"""
patterns/p19_over_qualification.py — Pattern 19: Over-qualification

检测：过度限定词
     - 非常 / 极为 / 极其
     - very / quite / extremely / highly
修复：删除
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class Match:
    start: int
    end: int
    matched_text: str
    suggested_fix: str  # "" 表示删除


ZH_PATTERNS = [
    r"极为",
    r"极其",
    r"十分",
    r"相当",
    r"格外",
    r"分外",
    r"尤为",
]

EN_PATTERNS = [
    r"\bvery\b",
    r"\bquite\b",
    r"\bextremely\b",
    r"\bhighly\b",
    r"\btremendously\b",
    r"\bexceedingly\b",
    r"\bexceptionally\b",
    r"\bremarkably\b",
    r"\babsolutely\b",
    r"\bcompletely\b",
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
