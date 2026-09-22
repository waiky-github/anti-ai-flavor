"""
patterns/p25_vagueness_by_design.py — Pattern 25: Vagueness by design

检测：刻意模糊（各种/许多/several）
     - 各种 / 诸多 / several / numerous
修复：要求具体化（纯规则无法自动具体化，只标记）
"""

from . import Match
import re
from typing import List


ZH_PATTERNS = [
    r"各种",
    r"诸多",
    r"若干",
    r"一些",
    r"某些",
    r"众多",
    r"大量",
    r"若干",
]

EN_PATTERNS = [
    r"\bnumerous\b",
    r"\bseveral\b",
    r"\bvarious\b",
    r"\bmany\b",
    r"\ba number of\b",
    r"\ba variety of\b",
    r"\bseveral\b",
    r"\bvarious\b",
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
    return text