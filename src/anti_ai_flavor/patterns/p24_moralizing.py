"""
patterns/p24_moralizing.py — Pattern 24: Moralizing

检测：道德化语言（必须/应该）
     - 我们必须 / 应该 / must / should
修复：改为客观陈述
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class Match:
    start: int
    end: int
    matched_text: str
    suggested_fix: str


ZH_PATTERNS = [
    r"我们必须",
    r"我们应该",
    r"大家应该",
    r"理应",
    r"务必要",
]

EN_PATTERNS = [
    r"we must",
    r"we should",
    r"you must",
    r"we have to",
    r"it is essential that",
    r"it is crucial that",
    r"it is imperative that",
]


def match(text: str) -> List[Match]:
    results = []
    
    # 中文
    for pattern in ZH_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, ""))
    
    # 英文
    for pattern in EN_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, ""))
    
    return results


def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]
