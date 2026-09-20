"""
patterns/p11_rhetorical_questions.py — Pattern 11: Rhetorical questions

检测：反问句（AI 常用修辞手法）
     - 但这是否意味着...？
     - 难道我们不应该...？
     - Isn't it true that...
修复：改为陈述句
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
    r"但这是否意味着",
    r"难道我们不应该",
    r"这难道不是",
    r"又怎能不",
    r"怎能不",
]

EN_PATTERNS = [
    r"isn't it (?:true|clear|obvious) that",
    r"doesn't it (?:make sense|follow) that",
    r"shouldn't we",
    r"how can we (?:not|ignore)",
    r"what if",
]


def match(text: str) -> List[Match]:
    results = []
    
    # 中文
    for pattern in ZH_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            # 只删除反问词，保留后面的陈述部分
            suggested = ""
            results.append(Match(start, end, full_match, suggested))
    
    # 英文
    for pattern in EN_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            suggested = ""
            results.append(Match(start, end, full_match, suggested))
    
    return results


def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]
