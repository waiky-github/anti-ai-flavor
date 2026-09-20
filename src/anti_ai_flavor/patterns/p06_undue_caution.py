"""
patterns/p06_undue_caution.py — Pattern 6: Undue caution

检测：过度谨慎的缓冲句
     - 有人可能会说
     - it could be argued
     - 有观点认为
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
    r"有人可能会说",
    r"有观点认为",
    r"有人可能会认为",
    r"不可否认的是",
    r"诚然",
    r"毋庸置疑",
]

EN_PATTERNS = [
    r"it could be argued",
    r"it has been argued",
    r"some might say",
    r"some would argue",
    r"one could argue",
    r"admittedly",
    r"it is often said",
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
