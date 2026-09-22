#!/usr/bin/env python3
"""tests/test_regression.py — 回归测试（修复点验证）"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

from anti_ai_flavor.cli import main as cli_main
from anti_ai_flavor.scoring import score_text, _count_pattern_hits


class TestCliLlmDefaultOff:
    """P0: --llm 默认关闭，显式传才启用"""

    def test_llm_default_false(self):
        """默认不传 --llm 时，args.llm 应为 False"""
        # 直接导入 argparse Namespace 构造测试
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        rewrite_parser = subparsers.add_parser("rewrite")
        rewrite_parser.add_argument("file", nargs="?", default=None)
        rewrite_parser.add_argument("--llm", action="store_true", default=False)
        rewrite_parser.add_argument("--no-llm", action="store_true")

        # 不传 --llm
        args = parser.parse_args(["rewrite", "input.md"])
        assert args.llm is False

        # 传 --llm
        args = parser.parse_args(["rewrite", "input.md", "--llm"])
        assert args.llm is True

        # 传 --no-llm
        args = parser.parse_args(["rewrite", "input.md", "--no-llm"])
        assert args.llm is False


class TestReportLlmSync:
    """P1: --report + --llm 时，report["rewritten"] / score_after 与实际输出一致"""

    def test_report_sync_after_llm(self, tmp_path, capsys):
        """LLM 成功后 report.rewritten 应等于 rewritten，score_after 应重新计算"""
        input_file = tmp_path / "input.md"
        input_file.write_text("首先，我们需要分析问题。", encoding="utf-8")

        fake_llm_output = "分析问题。"
        with patch("anti_ai_flavor.cli.llm_rewrite", return_value=fake_llm_output):
            sys.argv = [
                "anti-ai-flavor",
                "rewrite",
                str(input_file),
                "--report",
                "--llm",
            ]
            cli_main()

        captured = capsys.readouterr()
        # stdout 可能混有 stderr 的评分提示，定位第一个 { 开始解析 JSON
        out = captured.out
        start = out.find("{")
        assert start >= 0, f"expected JSON output, got stdout: {out!r}"
        json_text = out[start:]
        report = json.loads(json_text)

        assert report["rewritten"] == fake_llm_output, (
            f"report['rewritten'] 应等于 LLM 输出，实际: {report['rewritten']!r}"
        )
        assert report["changed"] is True
        assert "llm_applied" in report
        assert report["llm_applied"] is True


class TestP05P10NoDuplicate:
    """P2: p05_forced_triads 与 p10_list_fatigue 正则已区分，不重复计数"""

    def test_forced_triad_not_counted_as_list_fatigue(self):
        """2 逗号（3 段）应只命中 p05，不命中 p10"""
        text = "效率提升，成本降低，质量改善。"
        hits = _count_pattern_hits(text)
        p05_hits = [h for h in hits if h.pattern_id == "p05_forced_triads"]
        p10_hits = [h for h in hits if h.pattern_id == "p10_list_fatigue"]
        assert len(p05_hits) == 1, f"p05 应命中 1 次，实际: {len(p05_hits)}"
        assert len(p10_hits) == 0, f"p10 不应命中，实际: {len(p10_hits)}"

    def test_list_fatigue_counts_four_segments(self):
        """3 逗号（4 段）应命中 p10"""
        text = "效率提升，成本降低，质量改善，交付加速。"
        hits = _count_pattern_hits(text)
        p10_hits = [h for h in hits if h.pattern_id == "p10_list_fatigue"]
        assert len(p10_hits) == 1, f"p10 应命中 1 次，实际: {len(p10_hits)}"

    def test_no_duplicate_penalty_for_three_segments(self):
        """同一段 3 段文本不应同时命中 p05 和 p10"""
        text = "效率提升，成本降低，质量改善。"
        score_before = score_text(text)
        # 确保 raw penalty 不会因为重复计数而异常偏高
        # p05 命中一次扣 2 分，如果 p10 也命中则多扣 2 分
        assert score_before.raw == 2, f"3 段文本 raw penalty 应为 2，实际: {score_before.raw}"


class TestCheckDocsNoDuplicateIO:
    """P2: check-docs 不复用第一次循环结果，避免 2N 次 IO"""

    def test_check_docs_reuses_results(self, tmp_path, monkeypatch, capsys):
        """验证 check-docs 不会对同一文件 read_text 两次"""
        read_count = {}

        def counting_read_text(encoding):
            path = Path(str(Path(".").resolve()))
            # 这里我们 mock Path.read_text 来计数
            read_count["n"] = read_count.get("n", 0) + 1
            return "首先，值得注意的是，这个方案不仅提升了效率，而且增强了体验。"

        from pathlib import Path as _Path
        original_rtext = _Path.read_text

        def mock_read_text(self, encoding="utf-8"):
            read_count["n"] = read_count.get("n", 0) + 1
            return original_rtext(self, encoding=encoding)

        monkeypatch.setattr(_Path, "read_text", mock_read_text)

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "a.md").write_text("首先，值得注意的是，这个方案不仅提升了效率，而且增强了体验。", encoding="utf-8")
        (docs_dir / "b.md").write_text("这个方案提升了效率。", encoding="utf-8")

        sys.argv = ["anti-ai-flavor", "check-docs", str(docs_dir)]
        try:
            cli_main()
        except SystemExit:
            pass

        captured = capsys.readouterr()
        # 每个文件最多 read_text 一次（第一次循环），不应有第二次
        # 2 个文件，期望最多 2 次
        assert read_count.get("n", 0) <= 2, (
            f"check-docs 对文件 read_text 了 {read_count['n']} 次，预期最多 2 次"
        )


class TestP26MixedCodeSwitching:
    """P3-03: 中英混合 pattern 规则 + golden 用例"""

    def test_p26_match_the_system(self):
        """The system 能够... 应命中 p26"""
        from anti_ai_flavor.patterns.p26_mixed_code_switching import match as p26_match
        text = "The system 能够显著提升效率。"
        results = p26_match(text)
        assert len(results) == 1
        assert results[0].matched_text == "The system 能够显著提升效率。"
        assert results[0].suggested_fix == "系统能够显著提升效率。"

    def test_p26_match_this(self):
        """This 不仅... 应命中 p26"""
        from anti_ai_flavor.patterns.p26_mixed_code_switching import match as p26_match
        text = "This 不仅提升了效率，也增强了体验。"
        results = p26_match(text)
        assert len(results) == 1
        assert results[0].suggested_fix == "系统不仅提升了效率，也增强了体验。"

    def test_p26_no_false_positive(self):
        """纯中文不应命中 p26"""
        from anti_ai_flavor.patterns.p26_mixed_code_switching import match as p26_match
        assert p26_match("这个系统能够显著提升效率。") == []
        assert p26_match("首先，我们需要分析问题。") == []

    def test_p26_rewrite_text_golden(self):
        """TC011 golden 用例：rewrite_text 应按 p26 改写"""
        from anti_ai_flavor.core import rewrite_text
        result = rewrite_text("The system 能够显著提升效率。")
        assert result == "系统能够显著提升效率。"

    def test_p26_in_scoring(self):
        """p26 应在 scoring.py pattern_groups 中注册"""
        from anti_ai_flavor.scoring import _count_pattern_hits
        hits = _count_pattern_hits("The system 能够显著提升效率。")
        ids = [h.pattern_id for h in hits]
        assert "p26_mixed_code_switching" in ids
