#!/usr/bin/env python3
"""tests/test_watermark.py — 水印/异常字符检测与清理"""

import pytest

from anti_ai_flavor.watermark import detect_watermark, ZW_CHARS


@pytest.fixture
def clean_text():
    # 用英文逗号/句号，避免触发全角 ASCII 检测
    return "这是一个正常的中文文本,没有零宽字符."


class TestZeroWidthDetection:
    def test_zwsp_detected(self):
        text = "这是\u200b一个\u200b测试"
        result = detect_watermark(text, clean=False)
        assert result.zero_width_removed == 2
        assert "零宽" in result.warnings[0]

    def test_zwnj_detected(self):
        text = "这是\u200c测试"
        result = detect_watermark(text, clean=False)
        assert result.zero_width_removed >= 1

    def test_zwj_detected(self):
        text = "这是\u200d测试"
        result = detect_watermark(text, clean=False)
        assert result.zero_width_removed >= 1

    def test_bom_detected(self):
        text = "\ufeff这是一个带BOM的文本"
        result = detect_watermark(text, clean=False)
        assert result.bom_detected is True
        assert "BOM" in result.warnings[-1]

    def test_mixed_zero_width(self):
        text = "A\u200bB\u200cC\u200dD\ufeffE"
        result = detect_watermark(text, clean=False)
        assert result.zero_width_removed == 4
        assert result.bom_detected is True


class TestZeroWidthCleaning:
    def test_clean_removes_zw(self, clean_text):
        text = "这是\u200b测试"
        result = detect_watermark(text, clean=True)
        assert result.zero_width_removed == 1
        assert result.cleaned_text == "这是测试"

    def test_clean_removes_bom(self):
        text = "\ufeff文本"
        result = detect_watermark(text, clean=True)
        assert result.bom_detected is True
        assert result.cleaned_text == "文本"

    def test_clean_no_change(self, clean_text):
        result = detect_watermark(clean_text, clean=True)
        assert result.cleaned_text == clean_text
        assert result.zero_width_removed == 0
        assert result.bom_detected is False


class TestHomoglyph:
    def test_fullwidth_ascii_detected(self):
        text = "ＡＢＣ１２３"  # 全角 A B C 1 2 3
        result = detect_watermark(text, clean=False)
        assert "全角 ASCII" in result.warnings[0]

    def test_fullwidth_ascii_cleaned(self):
        text = "ＡＢＣ１２３"
        result = detect_watermark(text, clean=True)
        assert result.homoglyph_replaced >= 6
        assert result.cleaned_text == "ABC123"

    def test_no_homoglyphs_when_clean_false(self, clean_text):
        result = detect_watermark(clean_text, clean=False)
        assert result.homoglyph_replaced == 0
        assert "全角" not in " ".join(result.warnings)

    def test_no_homoglyphs_when_clean_true(self, clean_text):
        result = detect_watermark(clean_text, clean=True)
        assert result.homoglyph_replaced == 0


class TestSynthidSuspect:
    def test_high_frequency_character_warning(self):
        # 构造一个异常重复的文本
        text = "aaaaaaaaaa" * 30  # 10 个 a 重复 30 次
        result = detect_watermark(text, clean=False)
        # 非 CJK 文本不应触发 SynthID 提示
        assert result.synthid_suspect is False

    def test_normal_chinese_no_synthid_warning(self):
        text = "今天天气很好，我们去公园散步，遇到了一只可爱的小狗。"
        result = detect_watermark(text, clean=False)
        assert result.synthid_suspect is False
