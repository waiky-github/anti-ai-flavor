"""
patterns/p22_over_structuring.py — Pattern 22: Over-structuring

检测：过度结构化（第一点/第二点/第三点）
     - 第一点是...第二点是...
     - Point 1:... Point 2:...
修复：简化列表结构
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
    r"第[一二三四五]点[是为：:]",
    r"第[一二三四五]项[是为：:]",
    r"首先[，,].*?其次[，,].*?(?:最后|第三)",
]

EN_PATTERNS = [
    r"point\s+\d+[：:]",
    r"first[ly]?[，,].*?second[ly]?[，,].*?(?:finally|third)",
    r"1[.)]\s+.*?2[.)]\s+.*?3[.)]\s+",
]


def match(text: str) -> List[Match]:
    results = []
    
    # 中文
    for pattern in ZH_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, ""))
    
    # 英文
    for pattern in EN_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, ""))
    
    return results


def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]
