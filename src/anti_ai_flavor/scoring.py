#!/usr/bin/env python3
"""
anti_ai_flavor/scoring.py — 改写评分与报告

功能：
- score_text(text) -> dict：返回 0-100 分 + 命中 pattern 列表 + tier1 词扣分明细
- rewrite_with_report(text, scene="default") -> tuple[str, dict]：在 rewrite_text 之外包一层，不改原函数签名

设计：
- 不修改 core.py 的 rewrite_text()，保持向后兼容
- 评分只读分析，不改变文本
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .core import (
    TIER1_ZH,
    TIER1_EN,
    MECHANICAL_ORDERING,
    SYMMETRY_FILLERS,
    SYMMETRY_FILLERS_EN,
    SUMMARY_CLOSERS,
    SUMMARY_CLOSERS_EN,
    ABSTRACT_SUBJECTS,
    ABSTRACT_SUBJECTS_EN,
    FIXED_CONNECTORS_EN,
    rewrite_text,
    PATTERNS_AVAILABLE,
)
from .professionalism import compute_professionalism

try:
    from .patterns.tier1_legacy import IDIOM_FILLERS, DENSITY_FILLERS, REDUNDANT_MODIFIERS
except ImportError:
    IDIOM_FILLERS = []
    DENSITY_FILLERS = []
    REDUNDANT_MODIFIERS = []

# p05/p10 后处理用：抽象词集合拆两档（2026-09-28 A 阶段收窄误伤）
# 强信号 = 真黑话/AI 套话，单独出现即可判定
_STRONG_ABSTRACT_KEYWORDS = {
    "方面", "层面", "维度", "格局",
    "生态", "闭环", "全方位", "多维度", "多元化", "多层次",
    "赋能", "协同", "亮点",
    "变革", "转型",
    "引领",
    "全面", "深度", "高度", "广度", "全局",
    "全面性", "系统性", "整体性", "综合性", "智能化", "数字化", "数智化",
    "holistic", "comprehensive", "synergy", "leverage",
    "facilitate", "streamline", "robust",
    "scalable", "sustainable", "transformative", "paradigm",
}
# 弱信号 = 工程师/职场正常用词，不单独作为三段式判据
# （"优化性能、交付项目、核心模块" 在真实技术简历里是正常表达）
_WEAK_ABSTRACT_KEYWORDS = {
    "系统", "体系", "机制", "模式", "链路",
    "可持续", "价值", "优势", "特色",
    "创新", "升级", "优化", "提升", "改进", "增强",
    "驱动", "支撑", "展示", "反映", "推动",
    "高效", "稳定", "可扩展", "快速", "智能", "灵活", "精准",
    "整体", "核心", "关键",
    "降低", "改善", "加速", "交付", "简化",
    "systematic", "enhance", "optimize",
}
# 兼容旧引用
_ABSTRACT_KEYWORDS = _STRONG_ABSTRACT_KEYWORDS | _WEAK_ABSTRACT_KEYWORDS


@dataclass
class PatternHit:
    category: str
    pattern_id: Optional[str] = None
    matched_text: str = ""
    penalty: int = 0
    note: str = ""


@dataclass
class ScoreResult:
    score: int  # 0-100, 越高越好
    raw: int  # 原始扣分
    hits: List[PatternHit] = field(default_factory=list)
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


def _count_tier1_hits(text: str) -> List[PatternHit]:
    hits: List[PatternHit] = []
    # 中文 tier1
    for word in TIER1_ZH:
        if word in text:
            hits.append(PatternHit(
                category="tier1_zh",
                matched_text=word,
                penalty=5,
                note=f"Tier1 中文套话「{word}」",
            ))
    # 英文 tier1
    for word in TIER1_EN:
        base = word.rstrip('.,;:!?')
        if re.search(re.escape(base), text, flags=re.IGNORECASE):
            hits.append(PatternHit(
                category="tier1_en",
                matched_text=word,
                penalty=5,
                note=f"Tier1 英文套话「{word}」",
            ))
    return hits


def _count_legacy_hits(text: str) -> List[PatternHit]:
    hits: List[PatternHit] = []

    # 机械排序
    for pat in MECHANICAL_ORDERING:
        for m in re.finditer(pat, text):
            hits.append(PatternHit(
                category="mechanical_ordering",
                matched_text=m.group(),
                penalty=3,
                note="机械排序词",
            ))

    # 对称填充
    for pat in SYMMETRY_FILLERS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            hits.append(PatternHit(
                category="symmetry_fillers",
                matched_text=m.group(),
                penalty=4,
                note="对称填充结构",
            ))

    # 英文对称填充
    for pat in SYMMETRY_FILLERS_EN:
        for m in re.finditer(pat, text, re.IGNORECASE):
            hits.append(PatternHit(
                category="symmetry_fillers_en",
                matched_text=m.group(),
                penalty=4,
                note="英文对称填充",
            ))

    # 总结结尾
    for pat in SUMMARY_CLOSERS + SUMMARY_CLOSERS_EN:
        for m in re.finditer(pat, text, re.IGNORECASE):
            hits.append(PatternHit(
                category="summary_closers",
                matched_text=m.group(),
                penalty=3,
                note="总结性结尾",
            ))

    # 抽象主语
    for pat in ABSTRACT_SUBJECTS + ABSTRACT_SUBJECTS_EN + FIXED_CONNECTORS_EN:
        for m in re.finditer(pat, text, re.IGNORECASE):
            hits.append(PatternHit(
                category="abstract_subjects",
                matched_text=m.group(),
                penalty=3,
                note="抽象主语/固定衔接词",
            ))

    # 成语 filler
    for idiom in IDIOM_FILLERS:
        if idiom in text:
            hits.append(PatternHit(
                category="idiom_fillers",
                matched_text=idiom,
                penalty=3,
                note=f"成语 filler「{idiom}」",
            ))

    # 密度填充
    for pat in DENSITY_FILLERS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            hits.append(PatternHit(
                category="density_fillers",
                matched_text=m.group(),
                penalty=3,
                note="密度填充",
            ))

    # 冗余修饰词
    for pat in REDUNDANT_MODIFIERS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            hits.append(PatternHit(
                category="redundant_modifiers",
                matched_text=m.group(),
                penalty=2,
                note="冗余修饰词",
            ))

    return hits


def _count_pattern_hits(text: str) -> List[PatternHit]:
    """统计 25-pattern 体系的命中情况（只做轻量级正则统计，不执行 fix）。"""
    if not PATTERNS_AVAILABLE:
        return []

    hits: List[PatternHit] = []

    # 按优先级分组
    pattern_groups = [
        ("p01_not_x_but_y", r"不[仅只]?[^。]*?而[且却][^。]*?"),
        ("p02_one_line_closer", r"总之[^。]*?[。！]"),
        ("p03_staged_runup", r"我们需要[^。]*?[。！]\s*[^。]*?[。！]\s*[^。]*?[。！]"),
        ("p04_arguing_no_one", r"应该说[^。]*?[。！]"),
        # p05_forced_triads：3 个并列项，至少 1 项是抽象词
        # 中文并列分隔符：顿号 U+3001、全角逗号 U+FF0C、半角逗号 U+002C
        # 修复前误报严重：把 "Python、Shell、TCL" 这种技术栈列举也算成 AI 三段式
        # 修复后：要求并列项里至少 1 个是 _ABSTRACT_KEYWORDS 里的抽象词
        ("p05_forced_triads", r"(?:^|[。！？\n])\s*([^。\n]{2,30}?[、，,])\s*([^。\n]{2,30}?[、，,])\s*([^。\n]{2,30}?)[。！\n]"),
        ("p06_undue_caution", r"可能[^。]*?[。！]"),
        ("p07_artificial_imbalance", r"[^。]*?不仅[^。]*?而且[^。]*?[。！]"),
        ("p08_meta_commentary", r"值得注意的是[^。]*?[。！]"),
        ("p09_false_authority", r"研究表明[^。]*?[。！]"),
        # p10_list_fatigue：4 个以上并列项，至少 2 项是抽象词
        ("p10_list_fatigue", r"(?:^|[。！？\n])\s*([^。\n]{2,30}?[、，,])\s*([^。\n]{2,30}?[、，,])\s*([^。\n]{2,30}?[、，,])\s*([^。\n]{2,30}?)[。！\n]"),
        ("p11_rhetorical_questions", r"但这是否意味着[^。]*?[。？]"),
        ("p12_excessive_transitions", r"[^。]*?(?:此外|另外)[^。]*?[。！]"),
        ("p13_passive_overuse", r"(?:is|was|been)\s+(?:considered|believed|thought|found|discovered|shown)\s+(?:to\s+be)?[^。]*?[。.]"),
        ("p14_nominalization", r"(?:进行|做出)\s*[^。]*?(?:优化|改进|决定|选择|部署|实施)[^。]*?[。！]"),
        ("p15_abstract_subjects", r"(?:该技术的应用|该技术的实现|这一举措)[^。]*?[。！]"),
        ("p16_formulaic_closers", r"(?:综上所述|总之|简而言之)[^。]*?[。！]"),
        ("p17_forced_formality", r"(?:利用|运用|鉴于|遵照)\s*[^。]*?[。！]"),
        ("p18_repetition_rhythm", r"[^。]*?(?:高效|稳定|可扩展|fast|reliable|scalable)[^。]*?(?:、[^。]*?){2,}[。！]"),
        ("p19_over_qualification", r"(?:极为|极其|非常| highly|extremely|quite)\s*[^。]*?[。！]"),
        ("p20_stilted_coordination", r"既[^。]*?[，,][\s]*又[^。]*?[。！]"),
        ("p21_unnecessary_clarifications", r"(?:换句话说|换言之|in\s+other\s+words|that\s+is\s+to\s+say)[^。]*?[。！]"),
        ("p22_over_structuring", r"第[一二三四五][点项][是为：:][^。]*?[。！]"),
        ("p23_false_precision", r"\d+\.\d+%|数百万|数十亿|billions?\s+(?:of\s+)?(?:dollars|users|people)"),
        ("p24_moralizing", r"(?:我们必须|我们应该|大家应该|we\s+must|we\s+should)[^。]*?[。！]"),
        ("p25_vagueness_by_design", r"(?:各种|诸多|若干|numerous|several|various)[^。]*?[。！]"),
        ("p26_mixed_code_switching", r"(?:The system|The platform|Our team|This solution|This approach|This|That)\s+[^。]*?[。！]"),
    ]

    for pattern_id, pattern in pattern_groups:
        for m in re.finditer(pattern, text):
            # p05/p10 后处理（2026-09-28 精细化，治误伤）：
            # 区分点 = 整串是否「全是空洞宣称」，而非单纯含不含抽象词
            #   - 强黑话（赋能/闭环/全方位等）≥1 → 命中（真黑话单独出现即信号）
            #   - 无强黑话时：要求几乎全部并列项都是抽象词才命中
            #     "高效、稳定、可扩展" 3/3 抽象 → 抓
            #     "功能、性能、系统测试" 1/3 抽象 → 不抓（其余是具体测试类型）
            if pattern_id in ("p05_forced_triads", "p10_list_fatigue"):
                groups = m.groups()
                n = len(groups)
                strong_count = sum(
                    1 for g in groups
                    if any(w in g for w in _STRONG_ABSTRACT_KEYWORDS)
                )
                abstract_count = sum(
                    1 for g in groups
                    if any(w in g for w in _ABSTRACT_KEYWORDS)
                )
                # 无强黑话时，要求全部项都是抽象词（容忍至多 1 项具体）
                caught = strong_count >= 1 or abstract_count >= n
                if not caught:
                    continue

            hits.append(PatternHit(
                category="pattern",
                pattern_id=pattern_id,
                matched_text=m.group(),
                penalty=2,
                note=f"Pattern {pattern_id}",
            ))

    return hits


def score_text(text: str, *, weights: Optional[Dict[str, int]] = None) -> ScoreResult:
    """
    对文本进行 AI 味评分，返回 0-100 分（越高越好）。

    weights 可选：覆盖各类 penalty 权重。
    """
    if weights is None:
        weights = {
            "tier1_zh": 5,
            "tier1_en": 5,
            "mechanical_ordering": 3,
            "symmetry_fillers": 4,
            "symmetry_fillers_en": 4,
            "summary_closers": 3,
            "abstract_subjects": 3,
            "idiom_fillers": 3,
            "density_fillers": 3,
            "redundant_modifiers": 2,
            "pattern": 2,
        }

    all_hits: List[PatternHit] = []
    all_hits.extend(_count_tier1_hits(text))
    all_hits.extend(_count_legacy_hits(text))
    all_hits.extend(_count_pattern_hits(text))

    raw_penalty = sum(h.penalty for h in all_hits)

    # 密度归一化（2026-09-28 A 阶段）：按「每千字罚分」计分，与篇幅无关
    # norm = raw_penalty * 1000 / char_count
    # 同一段文本复制 N 次：raw ×N、char ×N，密度恒定（篇幅无关性）
    # 不用「保底 1000 字分母」——那会让重复短文的密度被线性放大
    char_count = max(1, len(text))
    norm_penalty = raw_penalty * 1000.0 / char_count

    # 归一化到 0-100（sqrt 衰减，避免线性封顶）：
    # - norm=0 → score=100
    # - norm=10 → score≈68
    # - norm=32 → score≈43
    # - norm=100 → score=0
    # 公式：score = 100 - sqrt(norm_penalty) * 10
    import math
    score = max(0, int(100 - math.sqrt(max(0.0, norm_penalty)) * 10))

    # 生成摘要
    if not all_hits:
        summary = "未检测到明显 AI 味特征"
    else:
        categories = {}
        for h in all_hits:
            categories.setdefault(h.category, 0)
            categories[h.category] += 1
        parts = [f"{k}: {v} 处" for k, v in sorted(categories.items())]
        summary = "命中 " + "；".join(parts)

    # 专业度评分（2026-09-28 新增）
    prof_result = compute_professionalism(text)

    details = {
        "raw_penalty": raw_penalty,
        "norm_penalty": round(norm_penalty, 2),
        "hit_count": len(all_hits),
        "hits_per_1k": round(len(all_hits) * 1000.0 / char_count, 2),
        "char_count": char_count,
        "categories": {h.category: h.matched_text for h in all_hits[:20]},
        "professionalism": prof_result.to_dict(),
    }

    return ScoreResult(
        score=score,
        raw=raw_penalty,
        hits=all_hits,
        summary=summary,
        details=details,
    )


def rewrite_with_report(text: str, scene: str = "default") -> Tuple[str, Dict[str, Any]]:
    """
    改写文本 + 返回报告。

    返回：
      (rewritten_text, {
        "original": str,
        "rewritten": str,
        "score_before": ScoreResult,
        "score_after": ScoreResult,
        "changed": bool,
      })
    """
    rewritten = rewrite_text(text, scene=scene)
    score_before = score_text(text)
    score_after = score_text(rewritten)

    report = {
        "original": text,
        "rewritten": rewritten,
        "score_before": {
            "score": score_before.score,
            "raw": score_before.raw,
            "summary": score_before.summary,
            "hits": [
                {
                    "category": h.category,
                    "pattern_id": h.pattern_id,
                    "matched_text": h.matched_text,
                    "penalty": h.penalty,
                    "note": h.note,
                }
                for h in score_before.hits
            ],
        },
        "score_after": {
            "score": score_after.score,
            "raw": score_after.raw,
            "summary": score_after.summary,
            "hits": [
                {
                    "category": h.category,
                    "pattern_id": h.pattern_id,
                    "matched_text": h.matched_text,
                    "penalty": h.penalty,
                    "note": h.note,
                }
                for h in score_after.hits
            ],
        },
        "changed": rewritten != text,
    }

    return rewritten, report
