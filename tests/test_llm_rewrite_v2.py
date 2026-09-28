#!/usr/bin/env python3
"""
tests/test_llm_rewrite_v2.py — v0.2.9.3 prompt 升级 + 长文本分段单测

覆盖：
- prompt 内容包含"拆句/具体动词/项目落地叙事/工程实施"等关键指令
- 少例（few-shot）完整不残缺
- _split_long_text 按段落/句子切分正确
- llm_rewrite 长文本自动分段（mock OpenAI）
- llm_rewrite 短文本保持单段调用（回归保护）
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from anti_ai_flavor.llm_rewrite import (
    SYSTEM_PROMPT,
    _build_user_prompt,
    _split_long_text,
    llm_rewrite,
)


# ---- prompt 内容断言 ----

def test_prompt_contains_landing_narrative():
    """新 prompt 必须明确要求「项目落地叙事」，这是 v0.2.9.3 升级核心。"""
    assert "项目落地叙事" in SYSTEM_PROMPT


def test_prompt_contains_split_sentence_directive():
    """新 prompt 必须强调拆句（v8 长难句是 AI 味儿主因）。"""
    assert "拆句" in SYSTEM_PROMPT


def test_prompt_contains_concrete_verb_rules():
    """新 prompt 必须给出"抽象→具体动词"的对照规则。"""
    # 至少要有 3 组对照
    for verb in ["打造/构建", "赋能/支撑", "提升/优化", "全方位/多维度"]:
        assert verb in SYSTEM_PROMPT, f"missing verb rule: {verb}"


def test_prompt_few_shot_example_intact():
    """few-shot 例必须完整（数字/技术栈原样保留），证明 LLM 有 in-context 参考。"""
    example = (
        "基于 4×A100 80GB，采用 vLLM 部署 Qwen3.6-27B，"
        "配置 FP8 量化、TP=4 张量并行及模型原生 MTP 推测解码；"
        "面向多并发推理场景完成推理引擎选型、量化调优与服务上线"
    )
    assert example in SYSTEM_PROMPT, "few-shot example truncated or modified"


def test_prompt_banned_phrases_listed():
    """禁止套话表必须包含我们之前漏掉的常见 AI 词。"""
    banned = [
        "不仅...而且",
        "更重要的是",
        "值得注意的是",
        "综上所述",
        "全方位",
        "多维度",
        "打造", "构建", "赋能", "协同", "助力",
        "数智化", "数字化转型",
    ]
    for word in banned:
        assert word in SYSTEM_PROMPT, f"banned word missing from prompt: {word}"

    # 2026-09-28 C 阶段：这些词从「绝对禁」改为「按语境判」，不应再在绝对禁词行
    # 它们仍会出现在 prompt 的「正常用词/带数字可保留」说明里
    for contextual in ["优化", "实现"]:
        assert contextual in SYSTEM_PROMPT
    # 确认 prompt 含「不要硬删」的语境判断说明
    assert "不要硬删" in SYSTEM_PROMPT


def test_prompt_unmodified_constraints():
    """prompt 必须明确写出「严格不改」的 4 类信息。"""
    for constraint in ["数字", "日期", "技术栈", "专有名词", "段落标题"]:
        assert constraint in SYSTEM_PROMPT, f"unmodified constraint missing: {constraint}"


# ---- _split_long_text 单测 ----

def test_split_short_text_unchanged():
    """短文本不切分。"""
    text = "短文本\n\n另一段"
    chunks = _split_long_text(text, max_chars=1700)
    assert chunks == [text]


def test_split_by_paragraphs():
    """按空行切：3 段各 600 字 → 总 1800 > 1700 → 切成 2 块。"""
    p1 = "段落1" + "a" * 600
    p2 = "段落2" + "b" * 600
    p3 = "段落3" + "c" * 600
    text = f"{p1}\n\n{p2}\n\n{p3}"
    chunks = _split_long_text(text, max_chars=1700)
    assert len(chunks) == 2
    # 第一块含 p1+p2，第二块 p3
    assert p1 in chunks[0] and p2 in chunks[0]
    assert p3 in chunks[1]


def test_split_long_paragraph_by_sentences():
    """单段超 max_chars 时按句号切（保留标点）。"""
    # 单段 3000 字符，按句号切
    sentences = [f"这是第{i}句话的内容。" for i in range(200)]  # ~1400 字符
    p = "".join(sentences)
    text = p + "\n\n" + "另一段"
    chunks = _split_long_text(text, max_chars=500)
    # 第一段被按句子切（多块），第二段独立
    assert len(chunks) >= 3
    # 验证每块都 < max_chars
    for c in chunks:
        assert len(c) <= 500


def test_split_preserves_content():
    """切分后拼接应等于原文（不允许丢字）。"""
    p1 = "段落1" + "a" * 500
    p2 = "段落2" + "b" * 500
    p3 = "段落3" + "c" * 500
    text = f"{p1}\n\n{p2}\n\n{p3}"
    chunks = _split_long_text(text, max_chars=800)
    # 拼接后空行归一化应等于原文（允许空行差异）
    joined = "\n\n".join(chunks)
    assert joined.replace("\n\n", "\n").replace("\n", "") == text.replace("\n\n", "\n").replace("\n", "")


# ---- llm_rewrite 端到端 mock ----

def _mock_openai_with_response(content: str):
    """构造一个返回 content 的 mock openai 包。"""
    mock_openai = MagicMock()
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))]
    )
    mock_openai.OpenAI.return_value = mock_client
    return mock_openai


def test_llm_rewrite_long_text_auto_split():
    """长文本自动分段 → 多次调用 → 合并返回。"""
    # 3 段各 600 字（共 1800+4 空行），max_chunk_chars=1700 应触发分段
    p1 = "段落1内容。" + "b" * 600
    p2 = "段落2内容。" + "c" * 600
    p3 = "段落3内容。" + "d" * 600
    text = f"{p1}\n\n{p2}\n\n{p3}"

    mock_openai = _mock_openai_with_response("改写后的文本。")

    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            result = llm_rewrite(text, api_key="sk-test", max_chunk_chars=800)

    # 验证调用了多次
    call_count = mock_openai.OpenAI.return_value.chat.completions.create.call_count
    assert call_count >= 2, f"expected ≥2 calls for long text, got {call_count}"
    # 验证返回包含每段改写
    assert "改写后的文本。" in result


def test_llm_rewrite_short_text_single_call():
    """短文本不触发分段（回归保护）。"""
    mock_openai = _mock_openai_with_response("短文本改写结果。")
    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            result = llm_rewrite("短文本", api_key="sk-test")
    # 只调用一次
    assert mock_openai.OpenAI.return_value.chat.completions.create.call_count == 1
    assert result == "短文本改写结果。"


def test_llm_rewrite_uses_system_role():
    """v0.2.9.3 改用 system + user 双角色（OpenAI 标准结构化 prompt 模式）。"""
    mock_openai = _mock_openai_with_response("OK。")
    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            llm_rewrite("test", api_key="sk-test")

    # 检查传给 LLM 的 messages 必须含 system + user
    call_kwargs = mock_openai.OpenAI.return_value.chat.completions.create.call_args
    messages = call_kwargs.kwargs["messages"]
    roles = [m["role"] for m in messages]
    assert "system" in roles, f"system role missing from {roles}"
    assert "user" in roles, f"user role missing from {roles}"
    # system 内容必须含"项目落地叙事"
    system_msg = next(m for m in messages if m["role"] == "system")
    assert "项目落地叙事" in system_msg["content"]


def test_llm_rewrite_prompt_includes_few_shot_to_llm():
    """few-shot 示例确实传给了 LLM（用户 prompt 里能看到例子的「前后对照」）。"""
    mock_openai = _mock_openai_with_response("OK。")
    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            llm_rewrite("test", api_key="sk-test")

    call_kwargs = mock_openai.OpenAI.return_value.chat.completions.create.call_args
    system_msg = next(
        m for m in call_kwargs.kwargs["messages"] if m["role"] == "system"
    )
    # 验证完整 few-shot 例子（含 4×A100 80GB 数字不丢）
    assert "4×A100 80GB" in system_msg["content"]
    assert "TP=4 张量并行" in system_msg["content"]
    assert "面向多并发推理场景" in system_msg["content"]


# ---- v0.2.11 项目细节补充 ----

def test_system_prompt_has_project_detail_rules():
    """v0.2.11 prompt 必须明确「项目细节补充规则」。"""
    assert "项目细节补充规则" in SYSTEM_PROMPT
    # 必须禁止"发明事实"
    assert "不发明事实" in SYSTEM_PROMPT or "原文为准" in SYSTEM_PROMPT


def test_build_user_prompt_no_context_returns_text_only():
    """无 project context 时，prompt 应只含待改写文本，不含「项目细节」块。"""
    prompt = _build_user_prompt("这是测试文本")
    assert "---待改写文本---" in prompt
    assert "这是测试文本" in prompt
    assert "项目细节" not in prompt


def test_build_user_prompt_with_project_context():
    """含 project_context 时，prompt 应附「项目细节（可选）」+ 通用细节块。"""
    ctx = "AI 平台项目是 5 人团队 3 个月搭起来，QPS 从 200 提到 1500"
    prompt = _build_user_prompt("原文内容", project_context=ctx)
    assert "---待改写文本---" in prompt
    assert "原文内容" in prompt
    assert "项目细节（可选）" in prompt
    assert "[通用细节]" in prompt
    assert ctx in prompt


def test_build_user_prompt_with_project_sections():
    """含 project_sections 时，prompt 应附「按段落标题」列表。"""
    sections = {
        "建设企业私有化 AI 平台": "团队 5 人，3 个月落地，对接 3 个业务线",
        "开发企业 AI 辅助工具链": "内部 100+ 研发使用，覆盖代码检索/文档问答",
    }
    prompt = _build_user_prompt("原文", project_sections=sections)
    assert "项目细节（可选）" in prompt
    assert "[按段落标题]" in prompt
    assert "建设企业私有化 AI 平台" in prompt
    assert "团队 5 人" in prompt
    assert "开发企业 AI 辅助工具链" in prompt


def test_build_user_prompt_with_both_context_and_sections():
    """通用细节 + 按段落标题同时提供时，prompt 应同时包含两个块。"""
    prompt = _build_user_prompt(
        "原文",
        project_context="通用事实",
        project_sections={"段1": "细节1"},
    )
    assert "[通用细节]" in prompt
    assert "通用事实" in prompt
    assert "[按段落标题]" in prompt
    assert "细节1" in prompt


def test_llm_rewrite_passes_project_context_to_llm():
    """project_context 必须透传到 LLM 的 user prompt。"""
    mock_openai = _mock_openai_with_response("OK。")
    ctx = "团队规模 5 人，2026 年 3 月上线"
    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            llm_rewrite("原文", api_key="sk-test", project_context=ctx)

    call_kwargs = mock_openai.OpenAI.return_value.chat.completions.create.call_args
    user_msg = next(
        m for m in call_kwargs.kwargs["messages"] if m["role"] == "user"
    )
    # 验证 LLM 实际收到了 project_context
    assert ctx in user_msg["content"]
    assert "项目细节" in user_msg["content"]


def test_llm_rewrite_passes_project_sections_to_llm():
    """project_sections 必须透传到 LLM 的 user prompt。"""
    mock_openai = _mock_openai_with_response("OK。")
    sections = {"建设企业私有化 AI 平台": "团队 5 人 3 个月搭起来"}
    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            llm_rewrite("原文", api_key="sk-test", project_sections=sections)

    call_kwargs = mock_openai.OpenAI.return_value.chat.completions.create.call_args
    user_msg = next(
        m for m in call_kwargs.kwargs["messages"] if m["role"] == "user"
    )
    assert "建设企业私有化 AI 平台" in user_msg["content"]
    assert "团队 5 人" in user_msg["content"]
    assert "[按段落标题]" in user_msg["content"]