"""
patterns/p01_not_x_but_y.py — Pattern 1: Not X but Y

检测：不是 A，而是 B / not X but Y / 并非 X，而是 Y
修复：直接保留后半句，删除对比结构
"""

from . import Match
import re
from typing import List

# 中文模式：不是...，而是... / 并非...，而是...
ZH_PATTERNS = [
    r"不是[^，,。]*?[，,][\s]*而是",
    r"并非[^，,。]*?[，,][\s]*而是",
    r"不是[^，,。]*?而是",  # 无逗号版本
]

# 英文模式：not X but Y / not just X, but Y
EN_PATTERNS = [
    r"not\s+(?:just\s+)?[^,]*?,\s*but\s+",
    r"not\s+(?!only\s)[^,]*?\s+but\s+(?!also)",
]

def match(text: str) -> List[Match]:
    """返回所有命中的 Match 列表"""
    results = []
    
    # 中文
    for pattern in ZH_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end_search = m.end()
            remaining = text[end_search:]
            end_match = re.search(r'[。！？\n]', remaining)
            if end_match:
                end = end_search + end_match.end()
            else:
                end = len(text)
            
            full_match = text[start:end]
            # 保留后半句：把"而是"换成"是"，否则会得到
            # "这玩意儿而是一个…"这种语法坏句。
            # （2026-09-30 实测发现：旧逻辑保留"而是"字样）
            eranwei_match = re.search(r'而是', full_match)
            if eranwei_match:
                fix_start = start + eranwei_match.start()
                tail = text[fix_start + 2:end]  # "而是"之后的内容
                suggested = "是" + tail
                suggested = suggested.strip()
            else:
                fix_start = m.end()
                suggested = text[fix_start:end].strip()
            results.append(Match(start, end, full_match, suggested))
    
    # 英文
    for pattern in EN_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end_search = m.end()
            remaining = text[end_search:]
            end_match = re.search(r'[.!?\n]', remaining)
            if end_match:
                end = end_search + end_match.end()
            else:
                end = len(text)
            
            full_match = text[start:end]
            suggested = text[m.end():end].strip()
            results.append(Match(start, end, full_match, suggested))
    
    return results

def fix(text: str, match_obj: Match) -> str:
    """应用修复：保留后半句"""
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]