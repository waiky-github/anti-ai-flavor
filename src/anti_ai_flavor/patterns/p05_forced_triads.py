"""
patterns/p05_forced_triads.py — Pattern 5: Forced triads

检测：强制三并列结构
     - A、B 和 C
     - A, B, and C
修复：保留，但标记为低优先级（不强制删除）
"""

from . import Match
import re
from typing import List

# 中文强制三并列（A、B 和 C）
ZH_TRIADS = [
    r"[^，,。\n]{2,6}[、][^，,。\n]{2,6}[和与及][^，,。\n]{2,6}",
]

# 英文强制三并列（A, B, and C）
EN_TRIADS = [
    r"[^,]{2,20},\s*[^,]{2,20},\s*and\s+[^,]{2,20}",
]

def match(text: str) -> List[Match]:
    """返回所有命中的 Match 列表"""
    results = []
    
    # 中文
    for pattern in ZH_TRIADS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            # 建议保留（只标记，不强制修改）
            results.append(Match(start, end, full_match, full_match))
    
    # 英文
    for pattern in EN_TRIADS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, full_match))
    
    return results

def fix(text: str, match_obj: Match) -> str:
    """
    应用修复：保留原文（不强制修改）。
    这个 pattern 只标记，不修改。
    """
    return text