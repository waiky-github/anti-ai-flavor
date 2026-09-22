"""
patterns/p18_repetition_rhythm.py — Pattern 18: Repetition for rhythm

检测：为了节奏而重复（三并列、四并列）
     - 高效、稳定、可扩展
     - fast, reliable, and scalable
修复：标记为低优先级，不强制修改
"""

from . import Match
import re
from typing import List


def match(text: str) -> List[Match]:
    results = []
    
    # 中文：X、Y 和 Z 或 X，Y，Z
    zh_pattern = r'[^，,。\n]{2,10}[、,][^，,。\n]{2,10}[、,][^，,。\n]{2,10}'
    for m in re.finditer(zh_pattern, text):
        start = m.start()
        end = m.end()
        full_match = text[start:end]
        results.append(Match(start, end, full_match, ""))
    
    # 英文：A, B, and C 或 A, B, C
    en_pattern = r'\b[A-Za-z]+(?:\s+[A-Za-z]+)*(?:,\s*[A-Za-z]+(?:\s+[A-Za-z]+)*)*(?:,?\s+and\s+[A-Za-z]+(?:\s+[A-Za-z]+)*)?'
    for m in re.finditer(en_pattern, text):
        start = m.start()
        end = m.end()
        full_match = text[start:end]
        # 只保留 3 个或以上并列项的
        if len(re.findall(r'[A-Za-z]+', full_match)) >= 3:
            results.append(Match(start, end, full_match, ""))
    
    return results

def fix(text: str, match_obj: Match) -> str:
    # 不修改，只标记
    return text