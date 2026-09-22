"""
anti_ai_flavor/rules.py — 规则词表与模式（统一数据源）

所有规则集中管理，供 core.py / scoring.py / detectors.py 共享。
"""

from .patterns.tier1_legacy import (
    TIER1_ZH,
    TIER1_EN,
    IDIOM_FILLERS,
    DENSITY_FILLERS,
    REDUNDANT_MODIFIERS,
)

# === 英文规则 ===

SYMMETRY_FILLERS_EN = [
    r"On one hand[\s\S]*?on the other hand[\s\S]*?[。.]",
    r"not only[^.]*but also[^.]*",
    r"both[^.]*and[^.]*",
]

ABSTRACT_SUBJECTS_EN = [
    r"The application of this technology[^.]*",
    r"This initiative helps[^.]*",
    r"On this basis[^,]*[,]",
    r"In a sense[^,]*[,]",
]

FIXED_CONNECTORS_EN = [
    r"It is important to note that[^.]*",
    r"It should be emphasized that[^.]*",
    r"It is worth mentioning that[^.]*",
]

SUMMARY_CLOSERS_EN = [
    r"In conclusion[^.]*",
    r"In summary[^.]*",
    r"To conclude[^.]*",
    r"Overall[^.]*",
    r"In the end[^.]*",
    r"Ultimately[^.]*",
]

# === 中文规则 ===

SYMMETRY_FILLERS = [
    r"一方面[^。]*另一方面[^。]*",
    r"既[^。]*又[^。]*",
    r"不仅[^。]*而且[^。]*",
    r"虽然[^。]*但[^。]*[^。]*",
]

MECHANICAL_ORDERING = [
    r"首先[,，]",
    r"其次[,，]",
    r"最后[,，]",
    r"First[,.]",
    r"Second[,.]",
    r"Third[,.]",
    r"Finally[,.]",
]

SUMMARY_CLOSERS = [
    r"综上所述",
    r"总而言之",
    r"简而言之",
    r"总的来说",
    r"由此可见",
    r"不难看出",
    r"具有重要意义",
]

ABSTRACT_SUBJECTS = [
    r"该技术的应用使得",
    r"这一举措有助于",
    r"在此基础上",
    r"从某种意义上说",
]

EM_DASH_OVERUSE = r"——\s*——"


__all__ = [
    "TIER1_ZH",
    "TIER1_EN",
    "IDIOM_FILLERS",
    "DENSITY_FILLERS",
    "REDUNDANT_MODIFIERS",
    "SYMMETRY_FILLERS_EN",
    "ABSTRACT_SUBJECTS_EN",
    "FIXED_CONNECTORS_EN",
    "SUMMARY_CLOSERS_EN",
    "SYMMETRY_FILLERS",
    "MECHANICAL_ORDERING",
    "SUMMARY_CLOSERS",
    "ABSTRACT_SUBJECTS",
    "EM_DASH_OVERUSE",
]
