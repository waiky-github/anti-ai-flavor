#!/usr/bin/env python3
"""tests/test_scoring.py — 评分模块"""

import pytest

from anti_ai_flavor.scoring import score_text, rewrite_with_report


class TestScoreText:
    def test_perfect_text_high_score(self):
        text = "这个功能提升了效率，也改善了体验。"
        result = score_text(text)
        assert result.score >= 80

    def test_tier1_zh_lowers_score(self):
        text = "值得一提的是，这个方案综上所述推动了整体发展。"
        result = score_text(text)
        assert result.score < 80
        assert any(h.category == "tier1_zh" for h in result.hits)

    def test_tier1_en_lowers_score(self):
        text = "Moreover, it is worth noting that this leverages a robust tapestry."
        result = score_text(text)
        assert result.score < 80
        assert any(h.category == "tier1_en" for h in result.hits)

    def test_mechanical_ordering_lowers_score(self):
        # 仅用英文机械排序词，避免命中中文 tier1「首先」
        text = "First, we should analyze the problem. Second, we must formulate a plan. Finally, we start executing."
        result = score_text(text)
        assert result.score < 80
        assert any(h.category == "mechanical_ordering" for h in result.hits)

    def test_summary_closers_lowers_score(self):
        text = "简而言之，结论很明显。"
        result = score_text(text)
        assert result.score < 80
        assert any(h.category == "summary_closers" for h in result.hits)

    def test_empty_text_perfect_score(self):
        result = score_text("")
        assert result.score == 100
        assert result.raw == 0

    def test_score_in_range(self):
        for text in [
            "正常文本，无套话。",
            "首先，值得注意的是，这个方案不仅提升了效率，而且增强了体验。",
            "In summary, it is important to note that this comprehensive solution serves as a game-changer.",
        ]:
            result = score_text(text)
            assert 0 <= result.score <= 100

    def test_summary_contains_categories(self):
        text = "值得一提的是，这个功能非常好用。"
        result = score_text(text)
        assert "tier1_zh" in result.summary


class TestRewriteWithReport:
    def test_returns_tuple(self):
        text = "首先，我们需要分析问题。"
        output = rewrite_with_report(text)
        assert isinstance(output, tuple)
        assert len(output) == 2
        rewritten, report = output
        assert isinstance(rewritten, str)
        assert isinstance(report, dict)

    def test_report_keys(self):
        text = "首先，我们需要分析问题。"
        _, report = rewrite_with_report(text)
        assert "original" in report
        assert "rewritten" in report
        assert "changed" in report
        assert "score_before" in report
        assert "score_after" in report

    def test_changed_true_when_rewritten(self):
        # 机械排序 + 冗余主语，确定会被改写
        text = "首先，我们需要分析问题。其次，我们要制定方案。最后，开始执行。"
        _, report = rewrite_with_report(text)
        assert report["changed"] is True

    def test_changed_false_when_clean(self):
        text = "这个功能提升了效率。"
        _, report = rewrite_with_report(text)
        assert report["changed"] is False

    def test_score_improves(self):
        text = "首先，我们需要分析问题。其次，我们要制定方案。最后，开始执行。"
        _, report = rewrite_with_report(text)
        assert report["score_after"]["score"] >= report["score_before"]["score"]
