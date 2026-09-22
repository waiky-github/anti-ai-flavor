"""
patterns/p08_meta_commentary.py — Pattern 8: Meta-commentary

检测：元评论（关于文本本身的评论）
     - 值得注意的是
     - It is worth noting
     - 需要强调的是
修复：删除
"""

from . import Match
import re
from typing import List


ZH_PATTERNS = [
    r"值得注意的是",
    r"需要强调的是",
    r"必须指出的是",
    r"我们可以看到",
    r"不难发现",
    r"众所周知",
    r"不言而喻",
]

EN_PATTERNS = [
    r"it is worth noting",
    r"it is important to note",
    r"it should be noted",
    r"it is worth emphasizing",
    r"one can see",
    r"it goes without saying",
    r"as we can see",
    r"it is evident that",
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