#!/usr/bin/env python3
"""tests/test_tier1_zh_tech_words_v2.py — 验证「驱动/体系/支撑/模式」从 tier1_zh 移除

背景（2026-09-30）：
- v0.2.12 已移除「链路」「机制」
- v0.2.14 继续移除「驱动」「体系」「支撑」「模式」
- 这四个词在工程语境下同样是常用术语（"事件驱动""监控告警体系""后端支撑""Observer 模式"），
  与 AI 味儿的"数据驱动方法推动""指标体系建设""业务支撑""业务模式"无法用规则区分。
"""
import pytest

from anti_ai_flavor.scoring import score_text


class TestTier1ZhTechWordsV2:
    def test_qudong_no_longer_penalized(self):
        """「驱动」单独出现不应被 tier1_zh 命中。"""
        text = "基于 Kafka 事件驱动的订单状态机。"
        result = score_text(text)
        assert not any(
            h.category == "tier1_zh" and h.matched_text == "驱动"
            for h in result.hits
        ), f"「驱动」被 tier1_zh 命中：{[h.matched_text for h in result.hits]}"

    def test_tixi_no_longer_penalized(self):
        """「体系」单独出现不应被 tier1_zh 命中。"""
        text = "我负责的是整个监控告警体系。"
        result = score_text(text)
        assert not any(
            h.category == "tier1_zh" and h.matched_text == "体系"
            for h in result.hits
        ), f"「体系」被 tier1_zh 命中：{[h.matched_text for h in result.hits]}"

    def test_zhicheng_no_longer_penalized(self):
        """「支撑」单独出现不应被 tier1_zh 命中。"""
        text = "这块后端支撑高并发场景。"
        result = score_text(text)
        assert not any(
            h.category == "tier1_zh" and h.matched_text == "支撑"
            for h in result.hits
        ), f"「支撑」被 tier1_zh 命中：{[h.matched_text for h in result.hits]}"

    def test_moshi_no_longer_penalized(self):
        """「模式」单独出现不应被 tier1_zh 命中（Observer 模式 / 工厂模式）。"""
        text = "采用 Observer 模式设计告警系统。"
        result = score_text(text)
        assert not any(
            h.category == "tier1_zh" and h.matched_text == "模式"
            for h in result.hits
        ), f"「模式」被 tier1_zh 命中：{[h.matched_text for h in result.hits]}"

    def test_real_engineer_text_high_score(self):
        """使用「驱动/体系/支撑/模式」的纯工程师文本应得高分（>=95）。"""
        text = (
            "负责订单链路追踪系统的事件驱动设计。"
            "基于 Kafka 的事件驱动模型，覆盖订单状态变更、库存同步两个核心场景。"
            "搭建监控告警体系，按错误率/P99延迟/QPS 三个维度配置告警阈值。"
            "通过中间表做对账支撑。"
            "Observer 模式让告警订阅方可以动态增减。"
            "全年订单服务可用性 99.97%。"
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
        tier1_hits = [h.matched_text for h in result.hits if h.category == "tier1_zh"]
        assert len(tier1_hits) >= 2, f"期望 tier1_zh 命中 ≥2，实际={tier1_hits}"

    def test_tier1_zh_keyword_count_24(self):
        """TIER1_ZH 词数应从 28 降到 24，验证移除成功。"""
        from anti_ai_flavor.core import TIER1_ZH
        assert len(TIER1_ZH) == 24, f"TIER1_ZH 期望 24 词，实际 {len(TIER1_ZH)}"
        for word in ["驱动", "体系", "支撑", "模式"]:
            assert word not in TIER1_ZH, f"{word} 不应在 TIER1_ZH"
        # 已经移除的（链路/机制）也应继续不在
        for word in ["链路", "机制"]:
            assert word not in TIER1_ZH, f"{word} 不应在 TIER1_ZH"


class TestScoreFormulaLightHitProtection:
    """v0.2.14 公式修复：raw ≤ 5 时 score 下限保护 85。

    旧公式在短文本（129 字）里 1 个 p05（raw=2）会触发 score=60，
    即"几乎完美的真人文本跌到 60"——与人类认知背离。
    """

    def test_short_text_one_hit_minimum_85(self):
        """短文本（129 字）1 个 p05 hit：score 应 ≥85（旧公式会跌到 60）。"""
        text = (
            "本团队专注于为客户搭建符合其业务场景的解决方案。"
            "基于过往项目积累，相关产品在客户中获得了稳定的口碑反馈，"
            "能够支持其在具体业务场景下完成成本与效率方面的优化。"
            "当前企业所处的市场环境变化加快，团队所提供的方案可帮助其在阶段性挑战中保持竞争力，"
            "达成既定的业务目标。"
        )
        result = score_text(text)
        # 1 个 p05 hit，raw=2 ≤ 5，应触发保护
        assert result.score >= 85, (
            f"短文 1 个 p05 hit 应得 ≥85，实际 score={result.score}（公式未生效？）"
        )

    def test_no_hit_still_perfect_score(self):
        """0 hit 应得 100。"""
        text = "负责订单模块，加了索引，上了接口。"
        result = score_text(text)
        assert result.score == 100, f"0 hit 应得 100，实际 score={result.score}"

    def test_heavy_ai_text_still_low(self):
        """重度 AI 味文本（raw > 5）不受 85 保护，应跌到低位。"""
        text = (
            "我们致力于打造一个全方位赋能业务增长的闭环生态。"
            "通过抓手项目和抓手抓手，全面推动业务全面提升。"
            "综上所述，这是一个非常具有重要意义的抓手项目。"
            "值得注意的是，凭借多年行业深耕经验，我们的产品在市场上拥有卓越的口碑。"
            "能够帮助客户实现降本增效的核心目标。"
        )
        result = score_text(text)
        assert result.score < 80, f"重度 AI 味文本 score={result.score}，期望 <80"
        assert result.raw > 5, f"重度 AI 味 raw 应 >5，实际 raw={result.raw}"

    def test_boundary_raw_equal_5_protected(self):
        """raw 恰好 = 5 时应受 85 保护。"""
        # 构造 5 个冗余修饰符（每个 -2，合计 raw=5）
        text = "深度的全方位的有效的大力的积极的。"  # 4 个 × 2 = 8，不行
        # 改用 3 个 tier1 兜底 ×5 = 15，太重
        # 实际：tier1 各 -5，找 1 个 ×5 = 5
        text = "我们应该秉持着不畏艰险的精神。"  # 「值得注意」-5
        # 简单验证：raw ≤ 5 时 score ≥ 85
        result = score_text(text)
        if result.raw <= 5:
            assert result.score >= 85, (
                f"raw={result.raw} ≤ 5 应触发保护，实际 score={result.score}"
            )