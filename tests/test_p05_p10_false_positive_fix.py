#!/usr/bin/env python3
"""tests/test_p05_p10_false_positive_fix.py — 验证 p05/p10 不再误报技术栈列举

2026-09-28 新增。修复前：
- p05/p10 regex 太宽，把 "Python、Shell、TCL、Verilog" 这种技术栈列举也算成 AI 三段式
- v9 测试样本被命中 18 次，误报率 100%

修复后：
- p05/p10 后处理：要求并列项里含抽象词
- "Python、Shell、TCL、Verilog" → 0 个抽象词 → 不命中
- "高效、稳定、可扩展" → 3 个抽象词 → 命中
"""

import pytest

from anti_ai_flavor.scoring import _count_pattern_hits, score_text


class TestP05P10FalsePositiveFix:
    def test_tech_stack_not_misreported(self):
        """技术栈列举不应被命中"""
        text = "Python/Shell/TCL/Verilog · FastAPI/Celery/RabbitMQ"
        hits = _count_pattern_hits(text)
        p05 = [h for h in hits if h.pattern_id == "p05_forced_triads"]
        p10 = [h for h in hits if h.pattern_id == "p10_list_fatigue"]
        assert len(p05) == 0, f"技术栈不应命中 p05，实际: {len(p05)}"
        assert len(p10) == 0, f"技术栈不应命中 p10，实际: {len(p10)}"

    def test_abstract_triad_still_caught(self):
        """抽象词三段式仍应命中（不误伤原意）"""
        text = "高效、稳定、可扩展。"
        hits = _count_pattern_hits(text)
        p05 = [h for h in hits if h.pattern_id == "p05_forced_triads"]
        assert len(p05) >= 1, f"抽象三段式应命中 p05，实际: {len(p05)}"

    def test_abstract_quad_still_caught(self):
        """抽象词四段式仍应命中"""
        text = "高效、稳定、可扩展、可持续。"
        hits = _count_pattern_hits(text)
        p10 = [h for h in hits if h.pattern_id == "p10_list_fatigue"]
        assert len(p10) >= 1, f"抽象四段式应命中 p10，实际: {len(p10)}"

    def test_mixed_tech_and_abstract(self):
        """混合（技术 + 抽象词）按「整串是否全是空洞宣称」判定（2026-09-28 精细化）"""
        # 0 抽象词：纯技术列举 → 不抓
        text1 = "Python、Shell、TCL、Verilog。"
        # 1 个弱抽象词混在 3 个具体技术词里 → 不抓（"高效"是正常质量词，不是黑话）
        text2 = "Python、Shell、高效、Verilog。"
        # 1 个强黑话混在技术词里 → 抓（"赋能"单独出现即 AI 黑话信号）
        text3 = "Python、Shell、赋能、Verilog。"
        h1 = _count_pattern_hits(text1)
        h2 = _count_pattern_hits(text2)
        h3 = _count_pattern_hits(text3)
        assert not any(x.pattern_id == "p10_list_fatigue" for x in h1)
        assert not any(x.pattern_id in ("p05_forced_triads", "p10_list_fatigue") for x in h2), \
            "1 个弱抽象词混入技术列举不应命中"
        assert any(x.pattern_id == "p10_list_fatigue" for x in h3), \
            "强黑话混入技术列举应命中"

    def test_rules_clean_reduces_ai_score(self):
        """规则清洗后 v8 → v8-rules，AI 味分应明显降低"""
        from anti_ai_flavor import rewrite_text
        v8_text = open("/tmp/aaf-ab/v8.txt").read()
        v8_rules = rewrite_text(v8_text)
        score_v8 = score_text(v8_text)
        score_rules = score_text(v8_rules)
        # 规则清洗后 raw 应降低（去掉 AI 味词）
        assert score_rules.raw < score_v8.raw, (
            f"v8-rules raw 应 < v8 raw，实际 rules={score_rules.raw}, v8={score_v8.raw}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
