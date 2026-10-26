"""库 API 的 scene="auto" 必须真的做识别（2026-10-26）。

踩坑记录：CLI 在调用前自己解析过场景，所以 ``--scene auto`` 看起来正常；
但直接调库 ``score_text(text, scene="auto")`` 时，``resolve_profile("auto")``
认不出这个 key → 静默回落 base。后果是：同一段文本走 CLI 判 social-note
（32 分 / block），走库 API 判 base（44 分），动作和分数全对不上，还查不出来。

本文件锁住「库 API 不许静默回落」这一条。
"""

from __future__ import annotations

import pathlib
import warnings

import pytest

from anti_ai_flavor.llm_rewrite import _build_messages
from anti_ai_flavor.profiles import resolve_profile, resolve_profile_for_text
from anti_ai_flavor.scoring import score_text

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
V3 = (FIXTURES / "promo_07_v3.txt").read_text(encoding="utf-8")
V9 = (FIXTURES / "promo_07_v9.txt").read_text(encoding="utf-8")


def test_auto_resolves_to_detected_scene():
    assert resolve_profile_for_text("auto", V3).name == "social-note"


def test_auto_matches_explicit_scene_in_scoring():
    auto = score_text(V3, scene="auto")
    explicit = score_text(V3, scene="social-note")
    assert auto.scene == explicit.scene == "social-note"
    assert auto.score == explicit.score
    assert auto.action == explicit.action


def test_auto_is_not_base_for_social_text():
    base = score_text(V3, scene="base")
    auto = score_text(V3, scene="auto")
    assert base.scene == "base"
    assert auto.scene != "base", "auto 静默回落 base = 场景判定形同虚设"
    assert auto.score != base.score, "场景生效后罚分应不同"


def test_auto_keeps_clean_text_passing():
    r = score_text(V9, scene="auto")
    assert r.scene == "social-note"
    assert r.score == 100
    assert r.action == "pass"


def test_auto_enables_scene_prompt_delta():
    auto_system = _build_messages(V9, scene="auto")[0]["content"]
    base_system = _build_messages(V9, scene="base")[0]["content"]
    assert len(auto_system) > len(base_system), "auto 应注入场景 prompt 增量"


def test_unknown_scene_warns_instead_of_silent_fallback():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        prof = resolve_profile("socialnotex")
    assert prof.name == "base"
    assert any(isinstance(w.message, RuntimeWarning) for w in caught), (
        "未知场景名必须发 RuntimeWarning，否则调用方无从发现写错了"
    )


@pytest.mark.parametrize("name", ["auto", "AUTO", " Auto ", "自动"])
def test_auto_spellings(name):
    assert resolve_profile_for_text(name, V3).name == "social-note"
