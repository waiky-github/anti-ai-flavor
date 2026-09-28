#!/usr/bin/env python3
"""tests/test_dedup.py — 结构层去重 / 多版合并 / 思维链剥离。

2026-09-28 新增（B 阶段）。覆盖：
- 精确重复段落去除
- 近似重复（措辞略改）去除，保留首版
- <think> 思维链块剥离
- 英文工作底稿剥离、正常中文正文保留
- 不误删技术名词 / 短英文行
"""
import pytest

from anti_ai_flavor.dedup import (
    deduplicate_text,
    _normalize_for_dedup,
    _strip_workpaper,
    _is_near_duplicate,
)


class TestExactDedup:
    def test_identical_paragraphs_removed(self):
        text = "第一段正文内容。\n\n第一段正文内容。\n\n第二段不同的正文。"
        out, stats = deduplicate_text(text, strip_workpaper=False)
        assert stats['removed_exact'] == 1
        assert out.count("第一段正文内容") == 1
        assert "第二段不同的正文" in out

    def test_no_duplicate_unchanged(self):
        text = "第一段正文。\n\n第二段正文。\n\n第三段正文。"
        out, stats = deduplicate_text(text, strip_workpaper=False)
        assert stats['removed_exact'] == 0
        assert stats['removed_near'] == 0
        assert stats['after_chars'] == stats['before_chars']


class TestNearDedup:
    def test_paraphrase_removed_keep_first(self):
        a = "建了企业私有化 AI 平台，团队 5 人，3 个月落地。"
        b = "建设企业私有化的 AI 平台，团队 5 人，3 个月落地。"
        out, stats = deduplicate_text(f"{a}\n\n{b}", strip_workpaper=False)
        assert stats['removed_near'] == 1
        assert a in out
        assert b not in out

    def test_genuinely_different_kept(self):
        a = "负责 AI 平台的架构设计与开发工作。"
        b = "负责存储芯片的功能测试和性能验证。"
        out, stats = deduplicate_text(f"{a}\n\n{b}", strip_workpaper=False)
        assert stats['removed_near'] == 0
        assert a in out and b in out

    def test_short_lines_not_fuzzy_deduped(self):
        # 短串不走模糊匹配，避免误删技术名词
        assert _is_near_duplicate(_normalize_for_dedup("Redis"),
                                  _normalize_for_dedup("Redux"), 0.9) is False


class TestThinkStrip:
    def test_think_block_removed(self):
        text = "<think>some long reasoning here</think>\n\n正文内容保留。"
        out = _strip_workpaper(text)
        assert "reasoning" not in out
        assert "正文内容保留" in out

    def test_huge_think_block_with_zh_inside_removed(self):
        # 思维链里即使含中文草稿，整块也应剥离（它不是最终成稿）
        text = "<think>Let me analyze。\n这是草稿内容。\n继续思考。</think>\n\n最终成稿。"
        out = _strip_workpaper(text)
        assert "草稿内容" not in out
        assert "最终成稿" in out

    def test_english_workpaper_lines_removed(self):
        text = ("Let me analyze this text carefully.\n"
                "Key things to do:\n"
                "中文正文要保留。\n"
                "Strict rules must be followed.")
        out = _strip_workpaper(text)
        assert "Let me analyze" not in out
        assert "中文正文要保留" in out

    def test_technical_english_kept(self):
        # 短技术名词 / 技术栈行不应被当底稿删掉
        text = "Python / Shell / TCL / Verilog\n\nvLLM / RAG / FastAPI"
        out = _strip_workpaper(text)
        assert "Python" in out
        assert "vLLM" in out

    def test_checkmark_lines_removed(self):
        text = "赋能 ✓ (not used)\n\n正常正文。"
        out = _strip_workpaper(text)
        assert "✓" not in out
        assert "正常正文" in out


class TestStatsShape:
    def test_stats_fields(self):
        text = "<think>x</think>\n\n重复。\n\n重复。"
        out, stats = deduplicate_text(text)
        for key in ('workpaper_chars_removed', 'removed_exact', 'removed_near',
                    'paragraphs_before', 'paragraphs_after',
                    'before_chars', 'after_chars'):
            assert key in stats
        assert stats['after_chars'] <= stats['before_chars']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
