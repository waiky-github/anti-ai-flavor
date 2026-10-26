"""
tests/test_scene_detector.py — 场景自动识别（三层架构第 1 层）

覆盖四类证据：

  1. 真实语料判对：小红书 v3/v5/v8/v9 正文 → social-note；README/PR → tech-doc；
     健康建议/科普 → health-content。
  2. 【核心回归】宠物健康题材的小红书正文**不得**被判成 health-content。
     这是 2026-10-26 改造中真实踩到的坑：按主题词计分时，v3/v8/v9 四版正文
     全部被 health-content 抢走，因为症状词+就医词累积超过体裁特征。
     修法是把「体裁」和「主题」分开判——health 场景只认对读者的祈使式建议。
  3. 低置信不硬猜：无特征文本、短句混写 → needs_confirmation=True 且 scene=base，
     同时保留 guessed_scene 供上层追问。
  4. 路径只做弱先验：路径写着 postmortem/health 但正文是小红书，仍判 social-note。

阈值常量在此锁定。改阈值必须同时改本文件并说明依据。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from anti_ai_flavor.profiles import detector as D  # noqa: E402
from anti_ai_flavor.profiles.detector import detect_scene, recognize  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _promo(version: str) -> str:
    return (FIXTURES / f"promo_07_{version}.txt").read_text(encoding="utf-8")


# ── 1. 真实语料判对 ──────────────────────────────────────────


@pytest.mark.parametrize("version", ["v3", "v5", "v8", "v9"])
def test_xiaohongshu_promo_is_social_note(version):
    g = detect_scene(_promo(version))
    assert g.scene == "social-note", f"{version} 判成 {g.scene}: {g.evidence[:5]}"
    assert not g.needs_confirmation
    assert g.confidence >= D.CONFIDENT_AT


def test_readme_is_tech_doc():
    g = detect_scene((REPO_ROOT / "README.md").read_text(encoding="utf-8")[:3000])
    assert g.scene == "tech-doc"
    assert not g.needs_confirmation


def test_pr_body_is_tech_doc():
    text = (
        "## 改动\n\n- 修复 `score_text` 的归一化\n- 新增 p38\n\n"
        "```python\nscore_text(x)\n```\n\n"
        "延迟从 820ms 降到 47ms，P99 见 src/anti_ai_flavor/scoring.py。"
    )
    g = detect_scene(text)
    assert g.scene == "tech-doc"
    assert "tech-doc:有代码块(+2.5)" in g.evidence


@pytest.mark.parametrize(
    "text",
    [
        "狗呕吐两天了，精神差。建议尽快就医，先做个血常规检查。本回答仅供参考，不能替代兽医诊断。",
        "猫皮肤真菌感染常见症状包括脱毛、红斑、瘙痒。一旦出现破溃应尽快就诊。日常需注意环境消毒，确诊需专业检查。",
    ],
)
def test_health_advice_is_health_content(text):
    g = detect_scene(text)
    assert g.scene == "health-content", g.to_dict()
    assert not g.needs_confirmation


# ── 2. 核心回归：体裁 ≠ 主题 ─────────────────────────────────


def test_pet_health_promo_is_not_health_content():
    """小红书宠物健康笔记含症状词与就医词，仍必须判 social-note。

    这是「按主题词计分」会翻车的经典 case：叙事正文里出现「医院/医生/脱毛」
    不等于它在给读者下医嘱。
    """
    text = _promo("v9")
    assert "医院" in text or "医生" in text  # 防御：样本确实含医疗词
    g = detect_scene(text)
    assert g.scene == "social-note", g.to_dict()
    # health 场景仍有分（主题相关），但不得反超
    assert g.scores["social-note"] > g.scores["health-content"]


def test_advice_regex_rejects_noun_usage():
    """「它给的建议就一句」是名词用法，不该触发 health 的祈使式建议信号。"""
    assert D._ADVICE_RE.search("它给的建议就一句，不客气也不吓人") is None
    assert D._ADVICE_RE.search("建议尽快就医") is not None
    assert D._ADVICE_RE.search("需注意环境消毒") is not None
    assert D._ADVICE_RE.search("请及时带去医院") is not None


# ── 3. 低置信不硬猜 ─────────────────────────────────────────


def test_empty_text_goes_base_without_asking():
    g = detect_scene("   ")
    assert g.scene == "base"
    assert g.confidence == 0.0
    assert g.guessed_scene is None


def test_featureless_text_needs_confirmation():
    g = detect_scene("今天天气不错。")
    assert g.scene == "base"
    assert g.needs_confirmation is True


def test_ambiguous_short_text_keeps_guess_for_ask():
    """混写短句：证据不够，回 base 但保留 guessed_scene，供 CLI 追问。"""
    g = detect_scene("我家猫吐了，我拍了照给小程序，它标了黄，让我去医院。")
    assert g.scene == "base"
    assert g.needs_confirmation is True
    assert g.guessed_scene == "social-note"
    scene, candidate = recognize("我家猫吐了，我拍了照给小程序，它标了黄，让我去医院。")
    assert scene == "base" and candidate == "social-note"


# ── 4. 路径只做弱先验 ───────────────────────────────────────


def test_path_prior_cannot_override_text():
    """路径里有 postmortem/health，但正文是小红书叙事 → 仍判 social-note。"""
    g = detect_scene(_promo("v9"), file_path="docs/health-postmortem-2026.md")
    assert g.scene == "social-note", g.to_dict()


def test_path_prior_breaks_tie_when_text_is_weak():
    """正文两边都弱时，路径先验可以推一把——这是它唯一的作用。"""
    weak = "修复了一个问题。"
    no_path = detect_scene(weak)
    with_path = detect_scene(weak, file_path="src/anti_ai_flavor/scoring.py")
    assert with_path.scores["tech-doc"] > no_path.scores["tech-doc"]


# ── 5. 结构与阈值锁定 ───────────────────────────────────────


def test_guess_to_dict_shape():
    d = detect_scene(_promo("v9")).to_dict()
    for key in ("scene", "confidence", "guessed_scene", "needs_confirmation", "evidence", "scores", "runner_up"):
        assert key in d
    assert isinstance(d["evidence"], list)


def test_thresholds_locked():
    """阈值是标定结果，不是随手写的。改动需重新标定并更新本断言。"""
    assert D.CONFIDENT_AT == 0.60
    assert D.MARGIN_AT == 0.15
    assert D.MIN_EVIDENCE == 2.0
    assert D.SCENE_TARGET == {"social-note": 6.0, "health-content": 5.0, "tech-doc": 5.0}
    assert D.PATH_PRIOR_WEIGHT < 1.0  # 必须弱于任何一条文本信号


def test_all_scene_signals_have_labels():
    for scene, signals in D.SCENE_SIGNALS.items():
        assert signals, f"{scene} 没有信号"
        for sig in signals:
            assert sig.label and sig.weight > 0
