"""对抗样本补漏的回归锁定 — 2026-10-26

背景：``scripts/acceptance_scene_2026_10_26.py`` 第一轮实测只命中 5/13，
逐条查根因后分三类处理，本文件把每一类的结论都锁死，防止以后改规则时回退。

  1. 引擎真漏检 → 补规则（p39 三段式排比 / p40 营销夸张腔 /
     p38 补「不仅仅是…更是一种」+ 空洞成长 / p33 补对偶否定）
  2. 判据写错 → 合规命中（p35/p37 跨场景）不算 raw 罚分，验收脚本改判据；
     领域闸门缺「医院/医生」等词导致 p37 在 social-note 漏检，补 markers
  3. 样本不真实 → 「破折号滥用」单句三连不构成滥用（p34 min_occurrences=2
     是对 span 计数），样本改成真实的一段里反复滥用

因为这些新规则都可能误伤正常人话，所以每条规则配一条负样本断言。
"""

from __future__ import annotations

import pytest

from anti_ai_flavor.scoring import score_text


def _ids(text: str, scene: str) -> list[str]:
    return [h.pattern_id or h.category for h in score_text(text, scene=scene).hits]


# ── 1. 引擎真漏检：补上的规则必须命中 ────────────────────────────────


@pytest.mark.parametrize(
    "text,expected,scenes",
    [
        # p39：两次递进否定 + 更是（底座规则，全场景生效）
        ("它不只是掉毛，不只是皮屑，更是身体在向你发出求救信号。",
         "p39_three_part_parallelism", ("social-note", "health-content", "base")),
        # p38 补：不仅仅是 X，更是一种 Y
        ("这不仅仅是养宠，更是一种生活方式的全面升级。",
         "p38_vague_elevation", ("social-note", "health-content", "base")),
        # p38 补：空洞成长（无「从 X 到 Y」的事实）
        ("经历过这次我成长了很多，也想把这些经验分享给大家。",
         "p38_vague_elevation", ("social-note", "health-content", "base")),
        # p33 补：对偶否定
        ("不是所有的秃斑都可怕，也不是所有的掉毛都能等。",
         "p33_contrastive_negation", ("social-note", "health-content", "base")),
        # p40：商品化夸张——场景专属，base 下按设计不生效
        ("谁懂啊家人们！这个神器的出现，直接让养宠幸福感拉满！",
         "p40_marketing_hype", ("social-note", "health-content")),
    ],
)
def test_gap_patterns_fire(text: str, expected: str, scenes: tuple[str, ...]) -> None:
    for scene in scenes:
        assert expected in _ids(text, scene), f"{expected} 在 {scene} 下未命中"


def test_p40_not_active_in_base() -> None:
    """营销夸张腔是场景专属规则，技术文档/base 下不该生效（避免性能文被误杀）。"""
    assert "p40_marketing_hype" not in _ids(
        "谁懂啊家人们！这个神器的出现，直接让养宠幸福感拉满！", "base"
    )


# ── 2. 领域闸门：合规红线跨场景生效靠 markers，补词后不能滥用 ─────────


def test_replace_doctor_without_pet_words_still_caught() -> None:
    """「不用去医院」本身没有宠物词，靠补的 markers（医院/医生）触发跨场景合规。"""
    result = score_text("有了它就不用去医院了，在家自己判断就行。", scene="social-note")
    assert result.compliance_hit is True


def test_tech_doc_medical_words_not_a_compliance_hit() -> None:
    """技术文档不写「医院/医生」，领域闸门必须照旧放行。"""
    result = score_text(
        "这次改动的目标是根治线上抖动，把重试队列的退避上限从 30s 降到 5s。",
        scene="tech-doc",
    )
    assert result.compliance_hit is False
    assert result.score == 100


# ── 3. 不误伤：补规则后的负样本 ─────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        # 单次递进不是三段式
        "这个过程不只是掉毛，更是换季。",
        "不只是猫，狗也会有这个问题。",
        # 正常并列否定，不是对偶否定骨架
        "他不是不想去，也不是没时间，是真买不到票。",
        # 带事实的成长不算空洞
        "我从不敢碰它到能自己上药，这中间练了半个月。",
        # 真人夸张（手感/撸猫），且没有商品化词
        "今天撸猫撸到手感拉满，它翻过来让我摸肚子。",
    ],
)
def test_gap_patterns_no_false_positive(text: str) -> None:
    assert score_text(text, scene="social-note").raw == 0, text


def test_tech_doc_performance_hype_not_flagged() -> None:
    """技术文档里的「性能拉满」不归营销夸张腔管（p40 只在表达/健康场景生效）。"""
    assert "p40_marketing_hype" not in _ids("把缓存层性能拉满后，P99 从 320ms 降到 90ms。", "tech-doc")


# ── 4. 破折号：单句三连不算滥用，一段里反复才算 ──────────────────────


def test_em_dash_single_sentence_not_abuse() -> None:
    """p34 的 min_occurrences 是对 span 计数，单句三连只构成 1 个 span。"""
    assert "p34_em_dash_abuse" not in _ids("那一刻我明白了——它不是在掉毛——它是在说话——它在求救。", "social-note")


def test_em_dash_paragraph_abuse_caught() -> None:
    text = (
        "那一刻我明白了——它不是在掉毛——它是在说话——它在求救。\n"
        "我坐在沙发上看了它很久——它趴着一动不动——我这才意识到——我错过了太多。"
    )
    assert "p34_em_dash_abuse" in _ids(text, "social-note")
