"""
profiles — 场景 profile 注册表与解析（2026-10-26）

## 用法

    from anti_ai_flavor.profiles import resolve_profile, activate_patterns

    prof = resolve_profile("social-note")     # 或旧别名 creative_doc / coder_pr …
    prof2 = resolve_profile("health_content")
    prof3 = resolve_profile("coder_pr")       # → tech-doc（别名解析）

    active = activate_patterns(prof)          # 本场景下生效的检测型 pattern 列表

## 向后兼容

旧代码里的场景名（coder_commit / coder_pr / ops_log / creative_doc …）全部保留为
别名，解析到对应的新场景，不会 KeyError。未知场景名统一回落 base，并在
``resolve_profile(...).name == "base"`` 时由调用方决定是否提示。
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from ..patterns import ALL_EXTENDED_PATTERNS, BASE_EXTENDED_PATTERNS
from ..patterns._extended import ExtendedPattern
from .base import BASE
from .scenes import HEALTH_CONTENT, SOCIAL_NOTE, TECH_DOC
from .schema import (
    ACTION_BLOCK,
    ACTION_PASS,
    ACTION_REWRITE,
    ACTION_WARN,
    ACTIONS,
    ActionPolicy,
    SceneMarkers,
    SceneProfile,
)

# 注册表顺序即优先级：具体场景在前，底座在最后兜底
PROFILES: List[SceneProfile] = [SOCIAL_NOTE, HEALTH_CONTENT, TECH_DOC, BASE]

PROFILE_BY_NAME: Dict[str, SceneProfile] = {p.name: p for p in PROFILES}

PATTERN_INDEX: Dict[str, ExtendedPattern] = {
    p.pattern_id: p for p in ALL_EXTENDED_PATTERNS
}

# 别名索引（含规范名自身）
ALIAS_INDEX: Dict[str, str] = {}
for _p in PROFILES:
    ALIAS_INDEX[_p.name] = _p.name
    for _a in _p.aliases:
        ALIAS_INDEX[_a] = _p.name


def resolve_profile(scene: str | None) -> SceneProfile:
    """场景名 / 别名 → SceneProfile。None 或未知名字回落 base。"""
    if not scene:
        return BASE
    key = str(scene).strip().lower().replace(" ", "-")
    name = ALIAS_INDEX.get(key)
    if name is None:
        # 再试一次把下划线统一成连字符
        name = ALIAS_INDEX.get(key.replace("_", "-"))
    if name is None:
        # 不静默：写错场景名要能让调用方看见，否则「以为按社交笔记判定、
        # 实际按底座判定」，分数和动作全错还查不出来
        if key not in ("auto", "自动", "default", "base"):
            import warnings

            warnings.warn(
                f"未知场景名 {scene!r}，已回落 base；可用场景：" + ", ".join(
                    p.name for p in PROFILES
                ),
                RuntimeWarning,
                stacklevel=2,
            )
        return BASE
    return PROFILE_BY_NAME[name]


def resolve_profile_for_text(scene: str | None, text: str) -> SceneProfile:
    """按「场景名 or auto」+ 文本 → SceneProfile。

    与 :func:`resolve_profile` 的区别：``scene == "auto"`` 时用文本跑场景识别，
    而不是静默回落 base。2026-10-26 补：库 API ``score_text(text, scene="auto")``
    曾静默落 base（CLI 自己在外面解析过所以看不出来），导致调用方以为用了场景
    判定、实际按底座打分——属于「静默 fallback」，必须显式处理。
    """
    key = str(scene or "").strip().lower().replace(" ", "-")
    if key in ("auto", "自动"):
        from .detector import detect_scene

        guess = detect_scene(text)
        return PROFILE_BY_NAME.get(guess.scene, BASE)
    return resolve_profile(scene)


def canonical_scene(scene: str | None) -> str:
    """别名 → 规范场景名。"""
    return resolve_profile(scene).name


def activate_patterns(profile: SceneProfile) -> List[ExtendedPattern]:
    """本场景下生效的检测型 pattern。

    规则：
      - 底座 pattern：默认生效，除非被 ``disabled_patterns`` 停用
      - 场景专属 pattern：只有 ``extra_patterns`` 里显式声明才生效
        （pattern 自身的 ``scenes`` 字段是第二道校验，两处必须一致）
    """
    active: List[ExtendedPattern] = []
    for p in BASE_EXTENDED_PATTERNS:
        if profile.is_disabled(p.pattern_id):
            continue
        active.append(p)
    for p in ALL_EXTENDED_PATTERNS:
        if p.pattern_id in profile.extra_patterns:
            if profile.is_disabled(p.pattern_id):
                continue
            if p not in active:
                active.append(p)
    return active


def cross_domain_compliance(
    text: str, active: SceneProfile,
) -> List[tuple[str, str]]:
    """跨场景合规扫描：其他场景的合规红线，在「文本属于该领域」时也生效。

    为什么需要这一层：场景识别可能判成 base（低置信），而合规红线是绝对的
    ——识别不准不该成为漏放「根治猫癣」「不用去医院」的理由。

    领域闸门（``SceneProfile.domain_markers``）避免反向误杀：技术文档写
    「根治线上抖动」不含宠物/健康领域词，不会被当医疗宣称拦下。

    返回 ``[(pattern_id, matched_text), ...]``；无命中返回空列表。
    """
    out: List[tuple[str, str]] = []
    if not text:
        return out
    for prof in PROFILES:
        if prof.name == active.name:
            continue
        if not prof.compliance_patterns:
            continue
        if prof.domain_markers and not any(m in text for m in prof.domain_markers):
            continue
        for pid in prof.compliance_patterns:
            pat = PATTERN_INDEX.get(pid)
            if pat is None:
                continue
            try:
                hit = pat.match(text)
            except Exception:
                continue
            if hit:
                out.append((pid, hit if isinstance(hit, str) else str(hit)))
    return out


def list_profiles() -> List[str]:
    """所有规范场景名（不含 base）。"""
    return [p.name for p in PROFILES if p.name != "base"]


__all__ = [
    "ACTION_PASS", "ACTION_WARN", "ACTION_REWRITE", "ACTION_BLOCK", "ACTIONS",
    "ActionPolicy", "SceneMarkers", "SceneProfile",
    "BASE", "SOCIAL_NOTE", "HEALTH_CONTENT", "TECH_DOC",
    "PROFILES", "PROFILE_BY_NAME", "ALIAS_INDEX",
    "resolve_profile", "resolve_profile_for_text", "canonical_scene",
    "activate_patterns", "list_profiles", "cross_domain_compliance",
]
