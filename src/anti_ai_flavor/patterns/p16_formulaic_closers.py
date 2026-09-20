"""
patterns/p16_formulaic_closers.py — Pattern 16: Formulaic closers

检测：公式化结尾
     - 总之 / 综上所述
     - In conclusion / To sum up
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
    r"综上所述",
    r"总之",
    r"总的来说",
    r"总括而言",
    r"一言以蔽之",
    r"简而言之",
]

EN_PATTERNS = [
    r"in conclusion",
    r"to sum up",
    r"to summarize",
    r"in summary",
    r"to conclude",
    r"overall",
    r"all in all",
    r"in a nutshell",
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
