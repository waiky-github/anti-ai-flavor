"""
patterns/p10_list_fatigue.py — Pattern 10: List fatigue

检测：机械排序（首先/其次/最后）
     - 首先...其次...最后
     - First... Second... Finally
修复：删除序数词，保留列表项
"""

from . import Match
import re
from typing import List

ZH_ORDINALS = [
    r"首先",
    r"其次",
    r"再次",
    r"最后",
    r"最后一点",
    r"第一步",
    r"第二步",
    r"第三步",
]

EN_ORDINALS = [
    r"first(?:ly)?",
    r"second(?:ly)?",
    r"third(?:ly)?",
    r"finally",
    r"lastly",
    r"in the first place",
    r"in the second place",
    r"to begin with",
    r"next",
]

def match(text: str) -> List[Match]:
    results = []
    
    # 中文
    for pattern in ZH_ORDINALS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            # 删除序数词，保留后面的逗号或内容
            suggested = ""
            results.append(Match(start, end, full_match, suggested))
    
    # 英文
    for pattern in EN_ORDINALS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            # 删除序数词，保留后面的逗号
            after = text[end:end+1]
            if after in [",", "，"]:
                suggested = ","
                end += 1
            else:
                suggested = ""
            results.append(Match(start, end, full_match, suggested))
    
    return results

def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]