"""
patterns/p13_passive_overuse.py — Pattern 13: Passive overuse

检测：过度使用被动语态（中文不明显，主要检测英文）
     - is considered / was found / it is believed
修复：改为主动语态
"""

from . import Match
import re
from typing import List

EN_PATTERNS = [
    r"is (?:considered|believed|thought|seen) (?:to be )?",
    r"was (?:found|discovered|shown) to be",
    r"it is (?:considered|believed|thought) that",
    r"it has been (?:shown|demonstrated|proven) that",
]

def match(text: str) -> List[Match]:
    results = []
    
    for pattern in EN_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            # 简化处理：标记为需要改为主动语态
            suggested = ""  # 纯规则无法自动改主动语态，留空表示需要人工或LLM处理
            results.append(Match(start, end, full_match, suggested))
    
    return results

def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]