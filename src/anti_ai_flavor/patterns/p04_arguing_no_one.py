"""
patterns/p04_arguing_no_one.py — Pattern 4: Arguing with no one

检测：虚假反驳句
     - 这不是关于 X
     - 这不仅仅是 X
     - 这不仅仅是关于 X
修复：删除虚假反驳，保留正面主张
"""

from . import Match
import re
from typing import List

# 中文虚假反驳
ZH_PATTERNS = [
    r"这不是关于[^。]*?[。]",
    r"这不仅仅是[^。]*?[。]",
    r"这并非[^。]*?[。]",
    r"这不能简单地说[^。]*?[。]",
]

# 英文虚假反驳
EN_PATTERNS = [
    r"It'?s not about[^.]*\.",
    r"It'?s not just[^.]*\.",
    r"This is not simply[^.]*\.",
    r"It'?s not that[^.]*\.",
]

def match(text: str) -> List[Match]:
    """返回所有命中的 Match 列表"""
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
    """应用修复：删除虚假反驳句"""
    return text[:match_obj.start] + text[match_obj.end:]