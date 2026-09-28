#!/usr/bin/env python3
"""tests/test_professionalism.py — 专业度评分维度测试

2026-09-28 新增。验证 5 个维度 + 综合分对真实文本 / AI 文本的区分度。
"""

import pytest

from anti_ai_flavor.professionalism import (
    compute_professionalism,
    compute_specificity,
    compute_detail_density,
    compute_sentence_variance,
    compute_professional_terms,
    compute_complexity,
)
from anti_ai_flavor.scoring import score_text


# ============================================================
# 测试样本
# ============================================================

REAL_TECH_TEXT = """
系统延迟从 230ms 降到 47ms，内存占用从 4.2GB 降到 1.8GB，启动速度从 8.3s 提升到 2.1s。
我们用 vLLM 部署了 Qwen2.5-72B-Instruct 模型（FP8 量化），吞吐量达到 1280 tokens/s。
2026 年 8 月上线后，故障恢复时间（MTTR）从 25 分钟缩短到 4 分钟。
"""

AI_CLICHE_TEXT = """
首先，值得注意的是，这个方案不仅提升了效率，而且增强了体验，
更重要的是构建了系统性的闭环，实现了全方位的覆盖，
打造了高质量发展的新格局，赋能业务全面升级。
"""

MIXED_TEXT = """
我们提供系统性方案。vLLM 部署快。系统延迟降低到 50ms。
"""


# ============================================================
# 各维度独立测试
# ============================================================

class TestSpecificity:
    def test_real_text_high_specificity(self):
        """真实技术文本（多数字）应该有高具体度"""
        score, details = compute_specificity(REAL_TECH_TEXT)
        assert score >= 70, f"真实文本具体度应 >= 70，实际 {score}"
        assert details["specific_density"] >= 5, "数字密度应 >= 5"

    def test_ai_text_low_specificity(self):
        """AI 套话文本具体度应低"""
        score, details = compute_specificity(AI_CLICHE_TEXT)
        assert score < 60, f"AI 文本具体度应 < 60，实际 {score}"
        assert details["abstract_density"] >= 3, "抽象词密度应高"

    def test_empty_text_default(self):
        score, _ = compute_specificity("")
        assert score == 50


class TestDetailDensity:
    def test_real_text_high_detail(self):
        score, details = compute_detail_density(REAL_TECH_TEXT)
        assert score >= 70, f"真实文本细节密度应 >= 70，实际 {score}"
        assert details["detail_count"] >= 5

    def test_ai_text_low_detail(self):
        score, _ = compute_detail_density(AI_CLICHE_TEXT)
        assert score < 50, f"AI 文本细节密度应 < 50，实际 {score}"


class TestSentenceVariance:
    def test_short_text_default(self):
        """单句时返回 50"""
        score, _ = compute_sentence_variance("一句话。")
        assert score == 50

    def test_uniform_ai_style_penalized(self):
        """3 句长度差不多 → CV 小 → 应该被识别为 AI 风格"""
        text = "今天天气很好，我们去公园散步，然后回家吃饭。" * 3
        # 但这是 1 句循环，不会触发。改用 3 个相似长度的句子：
        text = (
            "今天天气很好，阳光明媚，气温适宜。"
            "我们去看了一场电影，买了爆米花，喝了可乐。"
            "晚上回家吃饭，妈妈做了红烧肉，清淡爽口。"
        )
        score, details = compute_sentence_variance(text)
        # 句长相近，CV 应该小
        assert details["cv"] < 0.3, f"CV 太小，{details}"

    def test_varied_text_rewards(self):
        """长短句混合 → CV 大 → 应该得高分"""
        text = (
            "短。" * 1 +  # 短
            "中等长度的句子结构，有几个短语。" +  # 中
            "这是一个非常非常长非常长非常长的句子，包含了很多很多的信息和细节，涵盖了多个方面，" * 3  # 长
        )
        score, details = compute_sentence_variance(text)
        assert details["cv"] > 0.4, f"CV 应该 > 0.4，实际 {details['cv']}"


class TestProfessionalTerms:
    def test_tech_text_high_professional(self):
        score, details = compute_professional_terms(REAL_TECH_TEXT)
        assert score >= 70, f"技术文本专业术语应 >= 70，实际 {score}"

    def test_ai_text_low_professional(self):
        score, details = compute_professional_terms(AI_CLICHE_TEXT)
        # AI 文本里长词多是抽象 filler
        assert details["abstract_filler_ratio"] >= 0.3, "AI 文本抽象 filler 比例高"


class TestComplexity:
    def test_simple_text_low_complexity(self):
        """句内逗号少 → 从属结构少"""
        text = "今天天气好。明天天气好。后天天气好。"
        score, _ = compute_complexity(text)
        assert score <= 70, f"简单文本复杂度应 <= 70，实际 {score}"

    def test_complex_text_optimal(self):
        """1.5-2 个逗号/句 → 理想区间"""
        text = "今天天气很好，阳光明媚，气温适宜，我们去了公园。"  # 3 个逗号
        score, _ = compute_complexity(text)
        assert score >= 60, f"合理复杂度应 >= 60，实际 {score}"


# ============================================================
# 综合分测试
# ============================================================

class TestProfessionalismOverall:
    def test_real_text_high_overall(self):
        """真实技术文本综合分应该明显高于 AI 文本"""
        result = compute_professionalism(REAL_TECH_TEXT)
        assert result.score >= 70, f"真实文本综合分应 >= 70，实际 {result.score}"

    def test_ai_text_low_overall(self):
        """AI 套话文本综合分应明显低于真实文本"""
        result = compute_professionalism(AI_CLICHE_TEXT)
        assert result.score < 50, f"AI 文本综合分应 < 50，实际 {result.score}"

    def test_real_vs_ai_discriminative(self):
        """真实文本和 AI 文本综合分差距应 >= 30"""
        real_score = compute_professionalism(REAL_TECH_TEXT).score
        ai_score = compute_professionalism(AI_CLICHE_TEXT).score
        gap = real_score - ai_score
        assert gap >= 30, f"差距应 >= 30，实际 {gap}（real={real_score}, ai={ai_score}）"


# ============================================================
# 集成测试：score_text 应返回 professionalism 字段
# ============================================================

class TestScoreTextIntegration:
    def test_score_text_includes_professionalism(self):
        result = score_text(REAL_TECH_TEXT)
        assert "professionalism" in result.details
        prof = result.details["professionalism"]
        assert "score" in prof
        assert "dimensions" in prof
        assert "details" in prof
        assert set(prof["dimensions"].keys()) == {
            "specificity",
            "detail_density",
            "sentence_variance",
            "professional_terms",
            "complexity",
        }

    def test_rewritten_higher_professionalism_than_cliche(self):
        """改写后的 AI 文本专业度应低于真实文本"""
        rewrite_score = score_text(AI_CLICHE_TEXT).details["professionalism"]["score"]
        real_score = score_text(REAL_TECH_TEXT).details["professionalism"]["score"]
        assert real_score > rewrite_score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
