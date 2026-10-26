"""
profiles/detector.py — 场景自动识别（2026-10-26，三层架构第 1 层）

## 为什么重写

改造前 `core.auto_detect_scene()` 只看**文件路径关键词**（`"pr/"`、`"troubleshoot"`、
`"blog"`…）。三个问题：

  1. 小红书正文没有路径。粘进 CLI 的纯文本永远落到 "default"，等于没有场景。
  2. 路径会骗人。`docs/postmortem-pr-123.md` 同时命中三个规则，先匹配到的赢。
  3. 没有置信度。猜错了也照样按错的场景改写，用户看不出来。

## 现在怎么做

只看**文本特征**，路径只作为弱先验（权重 0.35，压不过任何一条文本特征）。
每个场景配一组可解释的信号，逐条加权求和 → 归一化成置信度：

    confidence = top_score / (sum_scores + 1.0)

分母 +1 是防「只有一条弱信号就报 100% 自信」：单条 1 分信号 → 1/2 = 0.5，
刚好在确认阈值上；两条独立信号 → 2/3 ≈ 0.67。

## 低置信不硬猜

用户 2026-10-26 拍板「低置信要问不硬猜」。所以：

  - confidence >= 0.60 且领先第二名 >= 0.15 → 直接用
  - 否则 `needs_confirmation=True`，交给上层决定（阶段 4：CLI 追问 / 网关默认 base）

绝不返回一个「大概吧」的场景去改用户的稿子——宁可问一句。

## 信号为什么是这些

全部来自实测：小红书 v3/v5/v8/v9 四版正文、本仓 README/PR body、宠物健康文案。
信号列表见 `SIGNALS`，每条都带 `label` 便于 CLI 输出「因为什么判成这样」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

# 判定阈值（2026-10-26 定，改动需同步 tests/test_scene_detector.py）
CONFIDENT_AT = 0.60      # 高于此值才敢直接用
MARGIN_AT = 0.15         # 领先第二名至少这么多
MIN_EVIDENCE = 2.0       # 低于此分视为「没什么可判的」

# 每个场景的「自评参考分」：该场景在真实语料上把信号拿满大约能到多少分。
# 定值依据（2026-10-26 实测）：
#   social-note    小红书 v3 正文命中 8 条中 5 条 → 5.5；v5 最高 6.5
#   health-content 健康回复/科普 4.5~5.3
#   tech-doc       README / PR body 4.5~5.0
# 置信度 = top / 参考分（封顶 0.97），含义是「这个场景的证据拿够了几成」，
# 而不是「在三个场景里占多少比重」——后者会让主题重叠的两类互相稀释
# （宠物健康类小红书同时含症状词与叙事特征，旧公式下四版正文全部低置信）。
SCENE_TARGET: Dict[str, float] = {
    "social-note": 6.0,
    "health-content": 5.0,
    "tech-doc": 5.0,
}

# 路径先验权重：故意低于任何一条文本信号的满分（1.0），
# 这样「路径说是技术文档」压不过「正文全是 emoji 和口语」。
PATH_PRIOR_WEIGHT = 0.35

_EMOJI_RE = re.compile(
    "[" "\U0001F300-\U0001FAFF" "\U00002600-\U000027BF" "\U0001F000-\U0001F2FF" "\u2B00-\u2BFF" "]"
)
_CODE_FENCE_RE = re.compile(r"```")
_INLINE_CODE_RE = re.compile(r"`[^`\n]{1,40}`")
_TAG_RE = re.compile(r"#[^\s#]{1,20}")
_URL_OR_PATH_RE = re.compile(r"(?:https?://|/[\w.-]+/)")
_VERSION_RE = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.M)
_CN_SENT_SPLIT = re.compile(r"[。！？!?\n]+")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")

# 「对读者给建议」只认祈使式，不认名词用法。
# 例：命中「建议尽快就医」「需注意消毒」「请及时就诊」；
#     不命中「它给的建议就一句」（"就"不是建议动词）（小红书正文里的名词用法，2026-10-26 实测误判源）
_ADVICE_RE = re.compile(
    r"(?:建议|最好)(?:尽快|及时|立即|马上|先|去|做|带|观察|就诊|就医|检查)"
    r"|(?:应|应当|需要)(?:尽快|及时|立即|注意|就医|就诊|检查|隔离|消毒)"
    r"|需(?:尽快|及时|注意|就医|就诊|检查|隔离|消毒)"
    r"|请(?:及时|尽快|立即|带|咨询|就医|就诊)"
    r"|(?:如|一旦)(?:出现|发现|有)[^。！？\n]{0,20}(?:应|请|需|立即|尽快)"
)


@dataclass(frozen=True)
class Signal:
    """一条可解释的文本信号。"""

    key: str
    label: str
    weight: float
    test: Callable[[str, Dict[str, float]], bool]


def _count(text: str, pattern: re.Pattern) -> int:
    return len(pattern.findall(text))


def _chars(text: str) -> int:
    return max(len(re.sub(r"\s", "", text)), 1)


# ── 特征池（先算一次，各信号共用）────────────────────────────────

def _features(text: str) -> Dict[str, float]:
    n = _chars(text)
    emoji = _count(text, _EMOJI_RE)
    sentences = [s for s in _CN_SENT_SPLIT.split(text) if s.strip()]
    avg_sent = (sum(len(s) for s in sentences) / len(sentences)) if sentences else 0.0
    latin = _count(text, _LATIN_WORD_RE)
    return {
        "chars": n,
        "emoji": emoji,
        "emoji_ratio": emoji / n * 1000,          # 每千字 emoji 数
        "first_person": text.count("我") / n * 1000,
        "colloquial": sum(text.count(w) for w in "啊吧呢嘛哈诶哎唉呀") / n * 1000,
        "avg_sent_len": avg_sent,
        "has_code_fence": 1.0 if _CODE_FENCE_RE.search(text) else 0.0,
        "inline_code": _count(text, _INLINE_CODE_RE),
        "tags": _count(text, _TAG_RE),
        "url_or_path": _count(text, _URL_OR_PATH_RE),
        "versions": _count(text, _VERSION_RE),
        "list_items": _count(text, _LIST_ITEM_RE),
        "latin_ratio": latin / n * 1000,
    }


# ── 场景信号表 ────────────────────────────────────────────────

SOCIAL_SIGNALS: Tuple[Signal, ...] = (
    Signal("emoji", "大量 emoji", 2.0, lambda t, f: f["emoji"] >= 3),
    Signal("emoji_dense", "emoji 密度高", 1.0, lambda t, f: f["emoji_ratio"] >= 8),
    Signal("tags", "带 #话题 标签", 1.5, lambda t, f: f["tags"] >= 2),
    Signal("first_person", "第一人称叙事", 2.0, lambda t, f: f["first_person"] >= 10),
    Signal(
        "narrative_action",
        "亲历动作句",
        1.0,
        lambda t, f: any(
            w in t for w in ("我拍", "我去", "我摸", "我带", "我找", "我家", "我翻", "我抱", "我问")
        ),
    ),
    Signal("colloquial", "口语语气词", 1.0, lambda t, f: f["colloquial"] >= 6),
    Signal("short_sent", "短句为主", 1.0, lambda t, f: 0 < f["avg_sent_len"] <= 20),
    Signal("no_code", "无代码块", 0.5, lambda t, f: f["has_code_fence"] == 0),
)

# 健康内容场景的判据是**语气**，不是主题词。
# 2026-10-26 实测教训：小红书宠物健康笔记同时含「脱毛/医院/医生」，
# 若按主题词计分，正文会被判成 health-content（v3/v8/v9 四版全中）。
# 体裁（个人经历叙事）和主题（宠物健康）必须分开判——所以这里只看
# 「是否在对读者下结论/给建议」，并要求非叙事口吻。
HEALTH_SIGNALS: Tuple[Signal, ...] = (
    Signal(
        "advice_form",
        "对读者给建议",
        1.5,
        lambda t, f: _ADVICE_RE.search(t) is not None,
    ),
    Signal(
        "symptom",
        "症状描述词",
        0.8,
        lambda t, f: any(
            w in t for w in ("症状", "脱毛", "红肿", "破溃", "瘙痒", "呕吐", "腹泻", "发热", "体温", "精神差")
        ),
    ),
    Signal(
        "medical_act",
        "就医/诊断动作",
        0.7,
        lambda t, f: any(
            w in t for w in ("就医", "就诊", "医院", "兽医", "医生", "诊断", "检查", "用药", "剂量", "疗程", "处方")
        ),
    ),
    Signal(
        "disclaimer",
        "免责/筛查表述",
        0.8,
        lambda t, f: any(w in t for w in ("不能替代", "仅供参考", "建议就医", "筛查", "初步判断")),
    ),
    Signal(
        "pet_context",
        "宠物主体",
        0.3,
        lambda t, f: any(w in t for w in ("猫", "狗", "宠物", "犬", "喵", "铲屎")),
    ),
    Signal("not_narrative", "非个人叙事口吻", 1.2, lambda t, f: f["first_person"] < 8),
)

TECH_SIGNALS: Tuple[Signal, ...] = (
    Signal("code_fence", "有代码块", 2.5, lambda t, f: f["has_code_fence"] >= 1),
    Signal("inline_code", "行内代码", 1.0, lambda t, f: f["inline_code"] >= 2),
    Signal("path", "文件路径/URL", 1.0, lambda t, f: f["url_or_path"] >= 2),
    Signal("version", "版本号", 0.5, lambda t, f: f["versions"] >= 1),
    Signal(
        "metric",
        "性能指标",
        1.0,
        lambda t, f: any(w in t for w in ("P99", "QPS", "延迟", "吞吐", "错误率", "CPU", "内存", "ms")),
    ),
    Signal("latin_heavy", "英文占比高", 1.0, lambda t, f: f["latin_ratio"] >= 120),
    Signal("lists", "结构化列表", 0.5, lambda t, f: f["list_items"] >= 3),
)

SCENE_SIGNALS: Dict[str, Tuple[Signal, ...]] = {
    "social-note": SOCIAL_SIGNALS,
    "health-content": HEALTH_SIGNALS,
    "tech-doc": TECH_SIGNALS,
}

# 路径弱先验：命中即加分（0.35），不再像旧版那样「先匹配先赢」
PATH_HINTS: Dict[str, Tuple[str, ...]] = {
    "tech-doc": ("pull/", "pr/", "merge_request", "commit", "troubleshoot", "debug", "postmortem", "src/", ".py", ".ts"),
    "social-note": ("blog", "article", "creative", "note", "xiaohongshu", "promotion", "post"),
    "health-content": ("health", "medical", "pet", "consult", "symptom"),
}


@dataclass
class SceneGuess:
    """识别结果。``needs_confirmation`` 为 True 时上层不该直接拿它去改稿。"""

    scene: str                 # 规范场景名；低置信时回 "base"
    confidence: float
    guessed_scene: Optional[str]  # 分数最高者（低置信时与 scene 不同，便于展示「我猜是 X」）
    needs_confirmation: bool
    evidence: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scene": self.scene,
            "confidence": round(self.confidence, 3),
            "guessed_scene": self.guessed_scene,
            "needs_confirmation": self.needs_confirmation,
            "evidence": list(self.evidence),
            "scores": {k: round(v, 2) for k, v in self.scores.items()},
            "runner_up": round(
                max((v for k, v in self.scores.items() if k != self.guessed_scene), default=0.0), 2
            )
            if self.guessed_scene
            else 0.0,
        }


def detect_scene(text: str, file_path: Optional[str] = None) -> SceneGuess:
    """按文本特征识别场景。路径只做弱先验。

    返回的 ``scene`` 在低置信时是 "base"（不硬猜）；``guessed_scene`` 保留原始猜测，
    供 CLI 追问「你这篇像 X，按 X 判吗？」使用。
    """
    if not text or not text.strip():
        return SceneGuess(
            scene="base",
            confidence=0.0,
            guessed_scene=None,
            needs_confirmation=False,
            evidence=["空文本"],
            scores={},
        )

    feats = _features(text)
    path_l = (file_path or "").lower()

    scores: Dict[str, float] = {}
    evidence: List[str] = []
    for scene, signals in SCENE_SIGNALS.items():
        score = 0.0
        for sig in signals:
            if sig.test(text, feats):
                score += sig.weight
                evidence.append(f"{scene}:{sig.label}(+{sig.weight})")
        # 路径弱先验
        if path_l and any(k in path_l for k in PATH_HINTS.get(scene, ())):
            score += PATH_PRIOR_WEIGHT
            evidence.append(f"{scene}:路径先验(+{PATH_PRIOR_WEIGHT})")
        scores[scene] = score

    top_scene, top_score = max(scores.items(), key=lambda kv: kv[1])
    total = sum(scores.values())

    if top_score < MIN_EVIDENCE:
        return SceneGuess(
            scene="base",
            confidence=0.0,
            guessed_scene=None,
            needs_confirmation=True,
            evidence=["无足够特征判定场景"],
            scores=scores,
        )

    target = SCENE_TARGET.get(top_scene, 5.0)
    confidence = min(top_score / target, 0.97)
    runner_up = max((v for k, v in scores.items() if k != top_scene), default=0.0)
    leading = (top_score - runner_up) / (top_score + 1.0)

    confident = confidence >= CONFIDENT_AT and leading >= MARGIN_AT
    return SceneGuess(
        scene=top_scene if confident else "base",
        confidence=confidence,
        guessed_scene=top_scene,
        needs_confirmation=not confident,
        evidence=evidence,
        scores=scores,
    )


def recognize(text: str, file_path: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """便捷版：返回 (生效场景, 候选场景)。生效场景低置信时是 base。"""
    guess = detect_scene(text, file_path)
    return guess.scene, (guess.guessed_scene if guess.needs_confirmation else None)


__all__ = [
    "Signal",
    "SceneGuess",
    "detect_scene",
    "recognize",
    "SOCIAL_SIGNALS",
    "HEALTH_SIGNALS",
    "TECH_SIGNALS",
    "SCENE_SIGNALS",
    "SCENE_TARGET",
    "PATH_HINTS",
    "CONFIDENT_AT",
    "MARGIN_AT",
    "MIN_EVIDENCE",
]
