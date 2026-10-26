"""场景感知评分（三层架构第 1、2 层）自测 — 2026-10-26

覆盖四类证据：

  1. 场景解析与 pattern 激活（别名 / 未知回落 / 场景专属 pattern 不串味）
  2. 13 条对抗样本（AI 味重）：至少 12 条命中，且命中的是**该命中的那条规则**
  3. 10 条负样本（真人叙事 / 技术文档 / 免责声明）：raw 必须为 0
  4. 真机校准：同一批素材的 v3（被打回）、v5（过渡稿）、v8/v9（发布稿）在
     social-note 场景下分数必须单调上升，且发布稿 100 分

第 4 类是这次改造的**验收核心**：如果评分器把用户实际打回的稿子判成高分，
或把实际发布的稿子判成低分，这套规则就没有资格当发布闸门。
"""

from pathlib import Path

import pytest

from anti_ai_flavor.profiles import (
    activate_patterns,
    list_profiles,
    resolve_profile,
)
from anti_ai_flavor.scoring import score_text

FIXTURES = Path(__file__).parent / "fixtures"


# ─────────────────────────────────────────────────────────────
# 1. 场景解析
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "alias,expected",
    [
        (None, "base"),
        ("default", "base"),
        ("base", "base"),
        ("unknown-xyz", "base"),
        ("social-note", "social-note"),
        ("social_note", "social-note"),
        ("xiaohongshu", "social-note"),      # 旧别名必须继续认
        ("creative_doc", "social-note"),
        ("health-content", "health-content"),
        ("health_content", "health-content"),
        ("tech-doc", "tech-doc"),
        ("coder_pr", "tech-doc"),            # 旧别名必须继续认
        ("ops_troubleshoot", "tech-doc"),
    ],
)
def test_resolve_profile_alias(alias, expected):
    assert resolve_profile(alias).name == expected


def test_list_profiles_excludes_base():
    names = list_profiles()
    assert "base" not in names
    assert set(names) == {"social-note", "health-content", "tech-doc"}


def test_health_only_patterns_do_not_leak_into_base():
    """合规红线 pattern 只能出现在 health-content —— 串到 base 会让所有场景误伤。"""
    base_ids = {p.pattern_id for p in activate_patterns(resolve_profile(None))}
    health_ids = {p.pattern_id for p in activate_patterns(resolve_profile("health-content"))}
    assert "p35_medical_claim" not in base_ids
    assert "p37_replace_doctor" not in base_ids
    assert {"p35_medical_claim", "p37_replace_doctor"} <= health_ids


def test_tech_doc_does_not_penalize_enumeration():
    """技术文档列举是正常结构，p32 不能进 tech-doc（否则 README 全挂）。"""
    tech_ids = {p.pattern_id for p in activate_patterns(resolve_profile("tech-doc"))}
    social_ids = {p.pattern_id for p in activate_patterns(resolve_profile("social-note"))}
    assert "p32_template_enumeration" not in tech_ids
    assert "p32_template_enumeration" in social_ids


# ─────────────────────────────────────────────────────────────
# 2. 对抗样本：13 条
# ─────────────────────────────────────────────────────────────

ADVERSARIAL = [
    # (用例名, 文本, 场景, 必须命中的 pattern_id)
    (
        "不是X而是Y",
        "这不是一只普通的猫，而是一个需要被理解的家人。它不是生病了，而是在向你求救。",
        "social-note",
        "p33_contrastive_negation",
    ),
    (
        "破折号插入语",
        "皮肤这块——毛发稀疏、皮肤暴露——需要留意。它——我的猫——一直在忍。",
        "social-note",
        "p34_em_dash_abuse",
    ),
    (
        "三件事模板枚举",
        "养猫要做三件事：第一，观察皮肤；第二，定期梳毛；第三，及时就医。",
        "social-note",
        "p32_template_enumeration",
    ),
    (
        "身体反应修辞",
        "看到那个黄标的一瞬间，我后背一凉，手心全是汗，眼眶一下子就热了。",
        "social-note",
        "p28_body_reaction",
    ),
    (
        "格言金句",
        "养猫这件事，说到底，是一场关于耐心的修行。",
        "social-note",
        "p29_maxim_golden_line",
    ),
    (
        "表演式坦诚",
        "说实话，我也不确定。老实讲，我也怕。坦白说，我犹豫了很久。",
        "social-note",
        "p30_staged_candor",
    ),
    (
        "修辞身份铺垫",
        "作为一个在宠物行业做了十年的从业者，我见过太多这样的案例。",
        "social-note",
        "p31_rhetorical_identity",
    ),
    (
        "绝对化用语",
        "这是市面上最好的猫藓方案，唯一有效，100%管用，养猫必备。",
        "social-note",
        "p36_absolute_claim",
    ),
    (
        "医疗功效宣称",
        "这个方案能根治猫藓，抗菌消炎，七天见效，彻底治愈不复发。",
        "health-content",
        "p35_medical_claim",
    ),
    (
        "替代医生",
        "有这个就不用去医院了，比医生说的还准，省钱省事。",
        "health-content",
        "p37_replace_doctor",
    ),
    (
        "时代共振空洞升华",
        "在当今这个快节奏的时代，我们不仅要关注宠物的身体健康，更要关注它们的情绪价值。"
        "让我们一起来探索这个充满温度的话题。",
        "social-note",
        "p38_vague_elevation",
    ),
    (
        "过度谨慎缓冲句",
        "有人可能会说，这只是偶然。有观点认为，不必过度解读。毋庸置疑，需要理性看待。",
        "social-note",
        "p06_undue_caution",
    ),
    (
        "对仗三段式",
        "效率提升，成本降低，质量改善。",
        "social-note",
        "p05_forced_triads",
    ),
]


def test_adversarial_samples_are_caught():
    """13 条对抗样本，至少 12 条命中；命中还必须是对的规则（不能靠别的水词蹭中）。"""
    caught = 0
    misses = []
    wrong_rule = []
    for name, text, scene, expected in ADVERSARIAL:
        result = score_text(text, scene=scene)
        ids = {h.pattern_id for h in result.hits if h.pattern_id}
        if expected in ids:
            caught += 1
        elif ids:
            wrong_rule.append((name, expected, sorted(ids)))
        else:
            misses.append((name, expected))
    assert caught >= 12, f"只命中 {caught}/13；漏检={misses}；规则错位={wrong_rule}"


def test_compliance_red_lines_block_regardless_of_score():
    """合规红线命中 → 无视分数直接 block（监管看字面，不看分数）。"""
    text = "这个方案能根治猫藓，抗菌消炎，七天见效。"
    for scene in ("health-content",):
        result = score_text(text, scene=scene)
        assert result.action == "block"
        assert any(h.pattern_id == "p35_medical_claim" for h in result.hits)


def test_same_text_different_scene_different_action():
    """同一句话在不同场景下处置不同 —— 这就是「场景智能」的实际意义。

    「真正的好猫粮，从来不是靠配料表堆出来的」：
      - 小红书正文 → 85 分 pass（单点金句，真人也会这么收尾）
      - 健康内容  → 85 分 warn（要出给用户的健康文案，金句=空话，必须提示）
    罚分都来自 p29，两场景都扣 4 分；差别来自 profile 的 warn_at 阈值。
    """
    text = "真正的好猫粮，从来不是靠配料表堆出来的。"
    social = score_text(text, scene="social-note")
    health = score_text(text, scene="health-content")
    assert social.score == health.score == 85  # 罚分一致
    assert "p29_maxim_golden_line" in {h.pattern_id for h in social.hits}
    assert social.action == "pass"
    assert health.action == "warn"             # 阈值不同 → 动作不同


def test_social_note_excuses_colloquialism():
    """口语在表达类内容是正常语域，不能扣分；技术文档里则要扣。"""
    text = "这玩意儿真的绝了，谁懂啊，家人们，这东西也太离谱了吧。"
    social = score_text(text, scene="social-note")
    tech = score_text(text, scene="tech-doc")
    assert social.raw < tech.raw


# ─────────────────────────────────────────────────────────────
# 3. 负样本：不能被扣分
# ─────────────────────────────────────────────────────────────

NEGATIVE = [
    ("真人叙事", "我家猫背上秃了一小块。我拍了张照，小程序标了黄，第二天去医院，医生说是猫癣。"),
    ("正常可能性表述", "可能是猫癣，也可能是过敏，具体要看医生怎么说。"),
    ("工程指标", "接口 P99 从 820ms 降到 47ms，错误率 99.97% 到 99.8%，QPS 提升 4.2 倍。"),
    ("技术栈列举", "双十一前做了三件事：①扩容到 32 核；②加了 Redis 缓存；③把慢查询从 14 条压到 0 条。"),
    ("免责声明", "它不是医生，也替代不了医生，有异常还是要去医院。"),
    ("序号建议", "第一次养猫先问医生，第二步再考虑换粮。最好先做个皮肤检查。"),
    ("数据库术语", "这个字段加了唯一索引，避免重复写入。"),
    ("短句叙事", "疼。就一个字。我抱着它坐了一路。"),
    ("普通并列", "毛毛有点糙，爪子有点干，其他都还行。"),
    ("英文技术", "We cache the token and retry with exponential backoff."),
]


@pytest.mark.parametrize("name,text", NEGATIVE, ids=[n for n, _ in NEGATIVE])
def test_negative_samples_score_zero(name, text):
    result = score_text(text)
    assert result.raw == 0, (
        f"{name} 被误伤：raw={result.raw}, "
        f"hits={[(h.pattern_id, h.matched_text) for h in result.hits]}"
    )
    assert result.score == 100


# ─────────────────────────────────────────────────────────────
# 4. 真机校准：v3 被打回 / v8、v9 发布
# ─────────────────────────────────────────────────────────────

def _load(ver: str) -> str:
    path = FIXTURES / f"promo_07_{ver}.txt"
    if not path.exists():
        pytest.skip(f"缺少校准样本 {path}")
    return path.read_text(encoding="utf-8")


def test_real_drafts_calibration_monotonic():
    """v3（用户打回）< v5（过渡）< v8/v9（发布成功），在 social-note 场景下必须单调。

    这条是「评分器有没有资格当发布闸门」的唯一硬证据。
    """
    scores = {v: score_text(_load(v), scene="social-note") for v in ("v3", "v5", "v8", "v9")}
    detail = {v: (r.score, r.raw) for v, r in scores.items()}
    assert scores["v3"].score < scores["v5"].score < scores["v8"].score, detail
    assert scores["v8"].score == 100, detail
    assert scores["v9"].score == 100, detail
    # 发布稿不能有任何命中；被打回的稿子必须有实质命中
    assert scores["v9"].raw == 0, detail
    assert scores["v3"].raw >= 10, detail


def test_real_drafts_action_matches_history():
    """动作分档要和历史事实一致：v3 该 block，v9 该 pass。"""
    assert score_text(_load("v3"), scene="social-note").action == "block"
    assert score_text(_load("v9"), scene="social-note").action == "pass"


def test_v3_hits_are_the_ones_user_complained_about():
    """v3 被用户批「AI 味很浓」时，命中的必须是那几类毛病（不是随便什么词）。"""
    result = score_text(_load("v3"), scene="social-note")
    ids = {h.pattern_id for h in result.hits if h.pattern_id}
    # 身体反应修辞 / 金句 / 表演式坦诚 —— v3 里的 AI 味主要来源
    assert "p28_body_reaction" in ids
    assert "p29_maxim_golden_line" in ids
    assert "p30_staged_candor" in ids


def test_scene_recorded_on_result():
    result = score_text("随便一句话。", scene="health-content")
    assert result.scene == "health-content"
    assert result.details["scene"] == "health-content"
    assert result.action in ("pass", "warn", "rewrite", "block")


def test_score_text_default_is_base():
    """不传 scene 时行为必须等于改造前的底座（向后兼容：219 项老测试靠这个）。"""
    result = score_text("接口 P99 从 820ms 降到 47ms。")
    assert result.scene == "base"
    assert result.raw == 0
