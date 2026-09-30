"""
patterns/p19_over_qualification.py — Pattern 19: Over-qualification

检测：过度限定词
     - 非常 / 极为 / 极其
     - very / quite / extremely / highly
修复：删除
"""

from . import Match
import re
from typing import List


ZH_PATTERNS = [
    r"极为",
    r"极其",
    r"十分",
    r"格外",
    r"分外",
    r"尤为",
    # 注：已移除裸"相当"。
    # "相当于"（等价于）是正常动词，旧规则裸删"相当"会把
    # "这就相当于把…"删成"这就于把…"，造成语法损坏；
    # "相当规模/相当水平"也是正常形容词。纯正则无法可靠区分，
    # 宁可不抓，不能误删。（2026-09-30 实测）
]

EN_PATTERNS = [
    r"\bvery\b",
    r"\bquite\b",
    r"\bextremely\b",
    r"\bhighly\b",
    r"\btremendously\b",
    r"\bexceedingly\b",
    r"\bexceptionally\b",
    r"\bremarkably\b",
    r"\babsolutely\b",
    r"\bcompletely\b",
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