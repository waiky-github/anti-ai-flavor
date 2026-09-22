"""
patterns/p23_false_precision.py — Pattern 23: False precision

检测：虚假精确数字（无来源的统计数据）
     - 99.9% / 数百万 / billions
修复：标记为需要验证（纯规则无法验证，只标记）
"""

from . import Match
import re
from typing import List


ZH_PATTERNS = [
    r"\d+\.\d+%",  # 99.9%
    r"数百万",
    r"数十亿",
    r"数百万亿",
    r" billions?",
    r" millions?",
]

EN_PATTERNS = [
    r"\d+\.\d+%",
    r"billions? (?:of )?(?:dollars|users|people)",
    r"millions? (?:of )?(?:dollars|users|people)",
    r" millions?",
    r" billions?",
    r"thousands? of",
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