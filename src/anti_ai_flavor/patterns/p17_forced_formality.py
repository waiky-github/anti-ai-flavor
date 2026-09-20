"""
patterns/p17_forced_formality.py — Pattern 17: Forced formality

检测：强制正式用语
     - 利用 / 运用
     - utilize / leverage
修复：改为口语化表达（利用→用，leverage→use）
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


ZH_MAPPING = {
    "利用": "用",
    "运用": "用",
    "实施": "做",
    "开展": "做",
    "推进": "推进",
    "赋能": "赋能",
    "构建": "建",
}

EN_MAPPING = {
    "utilize": "use",
    "leverage": "use",
    "implement": "do",
    "deploy": "use",
    "facilitate": "help",
    "commence": "start",
    "terminate": "end",
    "ascertain": "find",
    "methodology": "method",
    "utilization": "use",
}


def match(text: str) -> List[Match]:
    results = []
    
    # 中文
    for formal, informal in ZH_MAPPING.items():
        for m in re.finditer(re.escape(formal), text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, informal))
    
    # 英文
    for formal, informal in EN_MAPPING.items():
        for m in re.finditer(r'\b' + re.escape(formal) + r'\b', text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, informal))
    
    return results


def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]
