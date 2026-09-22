"""
patterns/p21_unnecessary_clarifications.py — Pattern 21: Unnecessary clarifications

检测：不必要的澄清（同义重复）
     - 换句话说 / 换言之
     - in other words / that is to say
修复：删除
"""

from . import Match
import re
from typing import List


ZH_PATTERNS = [
    r"换句话说",
    r"换言之",
    r"也就是说",
    r"换句话说讲",
    r"换句话说来",
]

EN_PATTERNS = [
    r"in other words",
    r"that is to say",
    r"i\.e\.",
    r"viz\.",
    r"to put it another way",
    r"to rephrase",
    r"in simpler terms",
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