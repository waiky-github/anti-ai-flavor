"""
patterns/__init__.py — 25-pattern 体系入口

每个 pattern 是一个独立模块，暴露：
  - name: str
  - match(text) -> list[Match]   # 返回命中的 span 列表
  - fix(match, text) -> str      # 返回修复后的文本
"""

from dataclasses import dataclass
from typing import List

from .tier1_legacy import TIER1_ZH, TIER1_EN


@dataclass
class Match:
    start: int
    end: int
    matched_text: str
    suggested_fix: str


# Pattern registry
from .p01_not_x_but_y import match as p01_match, fix as p01_fix
from .p02_one_line_closer import match as p02_match, fix as p02_fix
from .p03_staged_runup import match as p03_match, fix as p03_fix
from .p04_arguing_no_one import match as p04_match, fix as p04_fix
from .p05_forced_triads import match as p05_match, fix as p05_fix
from .p06_undue_caution import match as p06_match, fix as p06_fix
from .p07_artificial_imbalance import match as p07_match, fix as p07_fix
from .p08_meta_commentary import match as p08_match, fix as p08_fix
from .p09_false_authority import match as p09_match, fix as p09_fix
from .p10_list_fatigue import match as p10_match, fix as p10_fix
from .p11_rhetorical_questions import match as p11_match, fix as p11_fix
from .p12_excessive_transitions import match as p12_match, fix as p12_fix
from .p13_passive_overuse import match as p13_match, fix as p13_fix
from .p14_nominalization import match as p14_match, fix as p14_fix
from .p15_abstract_subjects import match as p15_match, fix as p15_fix
from .p16_formulaic_closers import match as p16_match, fix as p16_fix
from .p17_forced_formality import match as p17_match, fix as p17_fix
from .p18_repetition_rhythm import match as p18_match, fix as p18_fix
from .p19_over_qualification import match as p19_match, fix as p19_fix
from .p20_stilted_coordination import match as p20_match, fix as p20_fix
from .p21_unnecessary_clarifications import match as p21_match, fix as p21_fix
from .p22_over_structuring import match as p22_match, fix as p22_fix
from .p23_false_precision import match as p23_match, fix as p23_fix
from .p24_moralizing import match as p24_match, fix as p24_fix
from .p25_vagueness_by_design import match as p25_match, fix as p25_fix

__all__ = [
    "TIER1_ZH", "TIER1_EN",
    "p01_match", "p01_fix",
    "p02_match", "p02_fix",
    "p03_match", "p03_fix",
    "p04_match", "p04_fix",
    "p05_match", "p05_fix",
    "p06_match", "p06_fix",
    "p07_match", "p07_fix",
    "p08_match", "p08_fix",
    "p09_match", "p09_fix",
    "p10_match", "p10_fix",
    "p11_match", "p11_fix",
    "p12_match", "p12_fix",
    "p13_match", "p13_fix",
    "p14_match", "p14_fix",
    "p15_match", "p15_fix",
    "p16_match", "p16_fix",
    "p17_match", "p17_fix",
    "p18_match", "p18_fix",
    "p19_match", "p19_fix",
    "p20_match", "p20_fix",
    "p21_match", "p21_fix",
    "p22_match", "p22_fix",
    "p23_match", "p23_fix",
    "p24_match", "p24_fix",
    "p25_match", "p25_fix",
]
