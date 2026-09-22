#!/usr/bin/env python3
"""tests/test_property.py — 属性测试（hypothesis）"""

import pytest
from hypothesis import given, strategies as st

from anti_ai_flavor.scoring import score_text


class TestScoreTextProperties:
    """score_text 的通用属性"""

    @given(st.text())
    def test_score_always_in_range(self, text):
        """任意输入分数在 0-100"""
        result = score_text(text)
        assert 0 <= result.score <= 100

    @given(st.text())
    def test_empty_or_whitespace_never_crashes(self, text):
        """空串/空白/任意文本不崩溃"""
        result = score_text(text)
        assert result.score >= 0

    @given(st.text(min_size=1))
    def test_raw_penalty_non_negative(self, text):
        """raw penalty 非负"""
        result = score_text(text)
        assert result.raw >= 0

    @given(st.text())
    def test_summary_contains_score_when_hits(self, text):
        """有命中时 summary 含「命中」"""
        result = score_text(text)
        if result.hits:
            assert "命中" in result.summary
        else:
            assert "未检测到" in result.summary
