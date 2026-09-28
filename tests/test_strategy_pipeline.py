#!/usr/bin/env python3
"""tests/test_strategy_pipeline.py — --strategy 参数化改写管线测试

2026-09-28 新增。验证 4 种改写策略：
- rules（默认，向后兼容）：仅规则，无 LLM
- rules+llm：规则清洗 + LLM 后处理
- llm-only：直接 LLM，跳过规则
- auto：按 score_text 评分自动决策

所有 LLM 调用都用 unittest.mock 拦截，验证管线逻辑而不是真实 LLM 行为。
"""

import contextlib
import io
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from anti_ai_flavor.cli import main


def _run_cli(argv):
    """在隔离环境下运行 CLI，捕获 stdout/stderr。

    返回 (exit_code, stdout, stderr)。
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    old_argv = sys.argv
    sys.argv = argv

    env_backup = os.environ.get("ANTI_AI_LLM_API_KEY")

    try:
        with contextlib.redirect_stdout(stdout):
            with contextlib.redirect_stderr(stderr):
                try:
                    main()
                    exit_code = 0
                except SystemExit as e:
                    exit_code = e.code if isinstance(e.code, int) else 1
    finally:
        sys.argv = old_argv
        # 恢复 env（无论是否被 patch.dict 修改）
        if env_backup is None:
            os.environ.pop("ANTI_AI_LLM_API_KEY", None)
        else:
            os.environ["ANTI_AI_LLM_API_KEY"] = env_backup

    return exit_code, stdout.getvalue(), stderr.getvalue()


def _write_tmp(text: str) -> str:
    """写入临时文件，返回路径。"""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def _build_mock_openai(content: str = "LLM 重写后的文本。") -> MagicMock:
    """构造 mock openai 模块。"""
    mock_openai = MagicMock()
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))]
    )
    mock_openai.OpenAI.return_value = mock_client
    return mock_openai


def _patch_llm(mock_openai: MagicMock):
    """返回 (env_patch, sys_patch) 上下文管理器。

    用 clear=False 保留其它 env var（避免清掉 PYTHONPATH 等）。
    """
    return (
        patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": "test-key"}, clear=False),
        patch.dict("sys.modules", {"openai": mock_openai}),
    )


def test_strategy_rules_default():
    """默认（不传 --strategy）= rules，不调 LLM"""
    mock_openai = _build_mock_openai()
    tmp_path = _write_tmp("值得注意的是，这个方案不仅提升了效率，而且增强了体验。")
    env_p, sys_p = _patch_llm(mock_openai)
    try:
        with env_p, sys_p:
            exit_code, stdout, stderr = _run_cli([
                "prog", "rewrite", tmp_path, "--scene", "default",
            ])
        assert exit_code == 0
        assert mock_openai.OpenAI.call_count == 0
        # 规则清洗会删"值得注意的是"，输出不应该含这个词
        assert "值得注意的是" not in stdout
    finally:
        os.unlink(tmp_path)


def test_strategy_rules_plus_llm():
    """--strategy rules+llm = 规则清洗 + LLM 后处理"""
    mock_openai = _build_mock_openai()
    tmp_path = _write_tmp("我们致力于打造一个系统性的、全方位的闭环生态体系。")
    env_p, sys_p = _patch_llm(mock_openai)
    try:
        with env_p, sys_p:
            exit_code, stdout, stderr = _run_cli([
                "prog", "rewrite", tmp_path, "--strategy", "rules+llm",
            ])
        assert exit_code == 0
        assert mock_openai.OpenAI.called
        assert "LLM 重写后的文本。" in stdout
    finally:
        os.unlink(tmp_path)


def test_strategy_llm_only():
    """--strategy llm-only = 跳过规则，直接调 LLM"""
    mock_openai = _build_mock_openai()
    tmp_path = _write_tmp("随便什么文本。")
    env_p, sys_p = _patch_llm(mock_openai)
    try:
        with env_p, sys_p:
            exit_code, stdout, stderr = _run_cli([
                "prog", "rewrite", tmp_path, "--strategy", "llm-only",
            ])
        assert exit_code == 0
        assert mock_openai.OpenAI.called
        assert "LLM 重写后的文本。" in stdout
    finally:
        os.unlink(tmp_path)


def test_strategy_auto_skips_llm_when_score_high():
    """--strategy auto + 干净文本(score高) → 不调 LLM"""
    mock_openai = _build_mock_openai()
    tmp_path = _write_tmp("这个功能提升了效率，也改善了体验。代码经过测试，运行稳定。")
    env_p, sys_p = _patch_llm(mock_openai)
    try:
        with env_p, sys_p:
            exit_code, stdout, stderr = _run_cli([
                "prog", "rewrite", tmp_path, "--strategy", "auto",
                "--llm-trigger-threshold", "70",
            ])
        assert exit_code == 0
        assert mock_openai.OpenAI.call_count == 0
        assert "跳过 LLM" in stderr
    finally:
        os.unlink(tmp_path)


def test_strategy_auto_triggers_llm_when_score_low():
    """--strategy auto + AI 味文本(score低) → 触发 LLM"""
    mock_openai = _build_mock_openai()
    tmp_path = _write_tmp(
        "首先，值得注意的是，这个方案不仅提升了效率，而且增强了体验，"
        "更重要的是构建了系统性的闭环，实现了全方位的覆盖。"
    )
    env_p, sys_p = _patch_llm(mock_openai)
    try:
        with env_p, sys_p:
            exit_code, stdout, stderr = _run_cli([
                "prog", "rewrite", tmp_path, "--strategy", "auto",
                "--llm-trigger-threshold", "90",
            ])
        assert exit_code == 0
        assert mock_openai.OpenAI.called
        assert "auto 触发 LLM 兜底" in stderr
    finally:
        os.unlink(tmp_path)


def test_strategy_rules_plus_llm_fallback_when_llm_fails():
    """LLM 调用失败时 fallback 到纯规则结果，不报错退出"""
    mock_openai = MagicMock()
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("network timeout")
    mock_openai.OpenAI.return_value = mock_client

    tmp_path = _write_tmp("这是一个测试文本，包含一些 AI 味儿的句子。")
    env_p = patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": "test-key"}, clear=False)
    sys_p = patch.dict("sys.modules", {"openai": mock_openai})
    try:
        with env_p, sys_p:
            exit_code, stdout, stderr = _run_cli([
                "prog", "rewrite", tmp_path, "--strategy", "rules+llm",
            ])
        assert exit_code == 0
        assert "降级" in stderr
        assert len(stdout.strip()) > 0
    finally:
        os.unlink(tmp_path)


def test_backward_compat_llm_flag():
    """老的 --llm 参数仍然有效（等价于 --strategy rules+llm）"""
    mock_openai = _build_mock_openai()
    tmp_path = _write_tmp("我们致力于打造一个系统性的、全方位的闭环生态体系。")
    env_p, sys_p = _patch_llm(mock_openai)
    try:
        with env_p, sys_p:
            exit_code, stdout, stderr = _run_cli([
                "prog", "rewrite", tmp_path, "--llm",
            ])
        assert exit_code == 0
        assert mock_openai.OpenAI.called
        assert "LLM 重写后的文本。" in stdout
    finally:
        os.unlink(tmp_path)


def test_no_llm_flag_overrides_strategy():
    """--no-llm 即使在 --strategy rules+llm 下也不调 LLM"""
    mock_openai = _build_mock_openai()
    tmp_path = _write_tmp("我们致力于打造一个系统性的、全方位的闭环生态体系。")
    env_p, sys_p = _patch_llm(mock_openai)
    try:
        with env_p, sys_p:
            exit_code, stdout, stderr = _run_cli([
                "prog", "rewrite", tmp_path, "--strategy", "rules+llm", "--no-llm",
            ])
        assert exit_code == 0
        assert mock_openai.OpenAI.call_count == 0
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
