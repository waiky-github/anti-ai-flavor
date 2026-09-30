#!/usr/bin/env python3
"""tests/test_tier1_zh_tech_words_fix.py — 验证「链路」「机制」从 tier1_zh 移除后不再被误伤

背景（2026-09-30）：
- v0.2.11 重建四方对比时发现 v9_golden 标答因「链路/机制」被扣 10 分
- 这两个词是工程师正常术语（"链路追踪""告警机制""调用链路""事务机制"）
- 真人技术文本不该被扣分；空洞堆叠场景由密度/红海词组合兜底即可
"""
import pytest

from anti_ai_flavor.scoring import score_text


class TestTier1ZhTechWords:
    def test_lianlu_no_longer_penalized(self):
        """「链路」单独出现不应被 tier1_zh 命中。"""
        text = "在调用链路上加了 trace，定位慢调用方法。"
        result = score_text(text)
        assert not any(
            h.category == "tier1_zh" and h.matched_text == "链路"
            for h in result.hits
        ), f"「链路」被 tier1_zh 命中：{[h.matched_text for h in result.hits]}"

    def test_jizhi_no_longer_penalized(self):
        """「机制」单独出现不应被 tier1_zh 命中。"""
        text = "加了告警机制和重试机制，保证消息不丢。"
        result = score_text(text)
        assert not any(
            h.category == "tier1_zh" and h.matched_text == "机制"
            for h in result.hits
        ), f"「机制」被 tier1_zh 命中：{[h.matched_text for h in result.hits]}"

    def test_tech_text_high_score(self):
        """纯工程师叙事文本应得高分（>=95）。"""
        text = (
            "负责订单链路追踪，给核心接口加了 trace id。"
            "配告警机制按错误率/P99 延迟/调用量配阈值。"
            "上线后故障定位时间从 30 分钟缩到 3 分钟。"
            "全年订单服务可用性 99.97%（年度故障总时长 158 分钟，目标 12.5 小时）。"
        )
        result = score_text(text)
        assert result.score >= 95, f"score={result.score}，期望 ≥95，summary={result.summary}"

    def test_real_ai_text_still_penalized(self):
        """真正 AI 味儿文本（赋能/抓手/闭环 + 空洞结构）仍应被扣分。"""
        text = (
            "我们致力于打造一个全方位赋能业务增长的闭环生态。"
            "通过抓手项目和抓手抓手，全面推动业务全面提升。"
            "综上所述，这是一个非常具有重要意义的抓手项目。"
        )
        result = score_text(text)
        assert result.score < 80, f"AI 味儿文本 score={result.score}，期望 <80"
        # 至少命中 tier1_zh 一些强黑话
        tier1_hits = [h.matched_text for h in result.hits if h.category == "tier1_zh"]
        assert len(tier1_hits) >= 2, f"期望 tier1_zh 命中 ≥2，实际={tier1_hits}"

    def test_tier1_zh_keyword_count_decreased(self):
        """TIER1_ZH 词数应从 30 降到 28，验证移除成功。"""
        from anti_ai_flavor.core import TIER1_ZH
        assert len(TIER1_ZH) == 28, f"TIER1_ZH 期望 28 词，实际 {len(TIER1_ZH)}"
        assert "链路" not in TIER1_ZH
        assert "机制" not in TIER1_ZH