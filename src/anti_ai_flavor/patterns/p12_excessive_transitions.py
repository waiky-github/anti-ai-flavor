"""
patterns/p12_excessive_transitions.py — Pattern 12: Excessive transitions

检测：过度过渡词
     - 此外 / 另外 /  moreover / furthermore
     - 因此 / 于是 / therefore / thus
修复：删除或合并到前一句
"""

from . import Match
import re
from typing import List


ZH_TRANSITIONS = [
    r"此外",
    r"另外",
    r"与此同时",
    r"基于此",
    r"因此",
    r"于是",
    r"鉴于此",
    r"综上所述",
    r"总之",
    r"总的来说",
    r"从某种意义上说",
    r"从整体来看",
]

EN_TRANSITIONS = [
    r"furthermore",
    r"moreover",
    r"in addition",
    r"additionally",
    r"therefore",
    r"thus",
    r"consequently",
    r"as a result",
    r"in conclusion",
    r"to sum up",
    r"overall",
    r"in summary",
    r"it is important to note that",
    r"it is worth noting that",
    r"notably",
    r"significantly",
]

def match(text: str) -> List[Match]:
    results = []
    
    # 中文
    for pattern in ZH_TRANSITIONS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, ""))
    
    # 英文
    for pattern in EN_TRANSITIONS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, ""))
    
    return results

def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]