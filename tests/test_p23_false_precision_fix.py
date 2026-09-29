#!/usr/bin/env python3
r"""tests/test_p23_false_precision_fix.py — 验证 p23 假精确「只标记不扣分」不再误伤真人工程数字

2026-09-29 新增。修复前：
- scoring.py:271 硬编码 penalty=2，所有 pattern 一律扣 2 分
- p23 regex `\d+\.\d+%` 命中"99.97% 可用性/99.8% 成功率"等真实工程数字 → 误伤
- 盲测实测：Human 标答 99.97% 一处扣 2 分（score 65→63）；99.97%/99.8% 两处扣 4 分（score 100→0）

修复后：
- p23 命中 penalty=0（按 p23 docstring 原设计："纯规则无法验证，只标记"）
- 真实工程指标（99.97% 可用性/99.8% 成功率）不再被扣分
- AI 堆小数点百分比（86.4%/92.7%）仍被 hit 记录（details.hits 可见），但不扣分
- AI 兜底由 p05/p17/p07 等 15+ pattern 承担
"""

import pytest

from anti_ai_flavor.scoring import _count_pattern_hits, score_text


class TestP23FalsePositiveFix:
    def test_real_engineering_metric_not_penalized(self):
        """真实工程指标（99.97% 可用性/99.8% 成功率）不应被扣分"""
        text = "全年订单服务可用性 99.97%，下单成功率 99.8%。"
        score = score_text(text)
        # 真人叙事 + 真实指标 → 应满分
        assert score.score == 100, (
            f"真实工程指标 99.97%/99.8% 不应被扣分，实际 score={score.score}, "
            f"raw={score.raw}, summary={score.summary}"
        )

    def test_p23_hit_still_recorded_for_ai_text(self):
        """AI 编造小数点百分比时仍应被 hit 记录（信号可见，不扣分）"""
        text = "系统响应速度提升 86.4%，用户满意度达 92.7%。"
        hits = _count_pattern_hits(text)
        p23 = [h for h in hits if h.pattern_id == "p23_false_precision"]
        # hit 仍记录（信号可见）
        assert len(p23) >= 2, f"AI 编造 86.4%/92.7% 应被 hit 记录，实际 {len(p23)} 处"
        # 但 penalty 必须是 0（不扣分）
        for h in p23:
            assert h.penalty == 0, (
                f"p23 命中应 penalty=0（只标记），实际 penalty={h.penalty}"
            )

    def test_other_patterns_unaffected(self):
        """其他 pattern 仍按 penalty=2 扣分（不动它们）"""
        # "高效、稳定、可扩展" 触发 p05_forced_triads，p23 不应碰这条
        text = "系统高效、稳定、可扩展。99.97% 可用性。"
        score = score_text(text)
        # p05 仍应扣分（保持原行为）
        # 但 99.97% 不应额外扣分
        # 期望：仅 p05 扣 2 分，无 p23 扣分
        hits = _count_pattern_hits(text)
        p23_hits = [h for h in hits if h.pattern_id == "p23_false_precision"]
        assert all(h.penalty == 0 for h in p23_hits), "p23 命中一律 penalty=0"
        non_p23_penalties = [h.penalty for h in hits if h.pattern_id != "p23_false_precision"]
        # 其他 pattern 应保持 2 分（或 layer 权重对应值）
        # 测试只验证 p23 这一处，non-p23 penalty 不强制等于 2（受 weights 影响）
        assert len(non_p23_penalties) >= 1, "p05 应仍命中并扣分"

    def test_long_article_human_no_penalty_drain(self):
        """长文含多个 99.X% 真人指标时不应被 p23 累计扣分"""
        # 模拟博客 Human 标答（99.97%/99.8% 等多处小数百分比）
        text = (
            "负责电商平台订单模块的开发（Spring Boot + MySQL + Redis）。"
            "双十一前做了三件事："
            "① 给核心接口加了限流降级，大促当天峰值 QPS 6.8 万没挂；"
            "② 把慢查询翻了一遍，12 条核心 SQL 的延迟从秒级压到 100ms 以内；"
            "③ 写了监控脚本，故障发现时间从 12 分钟缩到 90 秒。"
            "全年订单服务可用性 99.97%，下单成功率 99.8%。"
        )
        score = score_text(text)
        # 不含其他 AI 黑话词 → 应满分（不靠 p23 误伤）
        assert score.score == 100, (
            f"真人叙事 + 多个 99.X% 工程指标不应被扣分，"
            f"实际 score={score.score}, raw={score.raw}"
        )

    def test_p23_hit_visible_in_details(self):
        """p23 hit 仍出现在 details.hits（信号可见）"""
        text = "AI 文案的 86.4% 提升是经典假精确。"
        score = score_text(text)
        hit_categories = {h.pattern_id for h in score.hits}
        assert "p23_false_precision" in hit_categories, (
            f"p23 hit 应在 details.hits 可见，实际 hit categories: {hit_categories}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])