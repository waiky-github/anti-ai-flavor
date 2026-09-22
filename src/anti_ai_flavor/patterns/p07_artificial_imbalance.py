"""
patterns/p07_artificial_imbalance.py — Pattern 7: Artificial imbalance

检测：不对称对比结构
     - 一方面...更重要的是
     - not only...but more importantly
修复：统一保留后半句（更重要/主要的那部分）
"""

from . import Match
import re
from typing import List

ZH_PATTERNS = [
    r"一方面[^，,。]*?[，,][\s]*更重要的是",
    r"不仅[^，,。]*?[，,][\s]*更重要的是",
]

EN_PATTERNS = [
    r"not only[^,]*?,\s*but more importantly",
    r"not just[^,]*?,\s*but more importantly",
]

def match(text: str) -> List[Match]:
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
            # 保留"更重要的是"后面的内容
            gengzhong_match = re.search(r'更重要的是', full_match)
            if gengzhong_match:
                fix_start = start + gengzhong_match.end()
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
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]