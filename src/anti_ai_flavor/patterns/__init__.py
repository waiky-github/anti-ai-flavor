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
from .p26_mixed_code_switching import match as p26_match, fix as p26_fix
from .p27_over_colloquial import match as p27_match, fix as p27_fix, assess as p27_assess

# === 检测型 pattern（p28+，2026-10-26 场景感知改造）===
# 与 p01–p27 的改写型不同：只有 match()，没有 fix()。
# 定位见 patterns/_extended.py 模块 docstring。
from .p28_body_reaction import PATTERN as P28_BODY_REACTION
from .p29_maxim_golden_line import PATTERN as P29_MAXIM_GOLDEN_LINE
from .p30_staged_candor import PATTERN as P30_STAGED_CANDOR
from .p31_rhetorical_identity import PATTERN as P31_RHETORICAL_IDENTITY
from .p32_template_enumeration import PATTERN as P32_TEMPLATE_ENUMERATION
from .p33_contrastive_negation import PATTERN as P33_CONTRASTIVE_NEGATION
from .p34_em_dash_abuse import PATTERN as P34_EM_DASH_ABUSE
from .p35_medical_claim import PATTERN as P35_MEDICAL_CLAIM
from .p36_absolute_claim import PATTERN as P36_ABSOLUTE_CLAIM
from .p37_replace_doctor import PATTERN as P37_REPLACE_DOCTOR
from .p38_vague_elevation import PATTERN as P38_VAGUE_ELEVATION
from .p39_three_part_parallelism import PATTERN as P39_THREE_PART_PARALLELISM
from .p40_marketing_hype import PATTERN as P40_MARKETING_HYPE

# 基础检测型 pattern 注册表：所有场景默认生效（scene="base"）
BASE_EXTENDED_PATTERNS = [
    P28_BODY_REACTION,
    P29_MAXIM_GOLDEN_LINE,
    P30_STAGED_CANDOR,
    P31_RHETORICAL_IDENTITY,
    P33_CONTRASTIVE_NEGATION,
    P34_EM_DASH_ABUSE,
    P36_ABSOLUTE_CLAIM,
    P38_VAGUE_ELEVATION,
    P39_THREE_PART_PARALLELISM,
]

# 场景专属 pattern：只在声明了对应场景时生效
SCENE_EXTENDED_PATTERNS = [
    P32_TEMPLATE_ENUMERATION,  # 表达类/健康内容；技术文档的枚举是正常结构
    P35_MEDICAL_CLAIM,         # health-content 专属，合规红线
    P37_REPLACE_DOCTOR,        # health-content 专属，合规红线
    P40_MARKETING_HYPE,        # 表达类/健康内容；技术文档的「性能拉满」不归它管
]

ALL_EXTENDED_PATTERNS = BASE_EXTENDED_PATTERNS + SCENE_EXTENDED_PATTERNS

EXTENDED_PATTERN_BY_ID = {p.pattern_id: p for p in ALL_EXTENDED_PATTERNS}

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
    "p26_match", "p26_fix",
    "p27_match", "p27_fix", "p27_assess",
    "BASE_EXTENDED_PATTERNS", "SCENE_EXTENDED_PATTERNS",
    "ALL_EXTENDED_PATTERNS", "EXTENDED_PATTERN_BY_ID",
]
