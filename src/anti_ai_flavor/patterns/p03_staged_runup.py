"""
patterns/p03_staged_runup.py — Pattern 3: Staged run-up

检测：段首铺垫句
     - 让我们深入了解
     - 值得注意的
     - 首先
修复：删除，直接陈述
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


# 中文段首铺垫词
ZH_RUNUPS = [
    r"值得注意的[，,]",
    r"让我们[^。]*?[，,]",
    r"首先[，,]",
    r"毋庸置疑[，,]",
    r"众所周知[，,]",
    r"不难发现[，,]",
    r"不难看出[，,]",
    r"不难理解[，,]",
    r"不难想象[，,]",
]

# 英文段首铺垫词
EN_RUNUPS = [
    r"It is important to note that",
    r"It should be emphasized that",
    r"It is worth mentioning that",
    r"Let's dive into",
    r"Let's take a closer look",
    r"First and foremost",
    r"Needless to say",
    r"As we all know",
]


def match(text: str) -> List[Match]:
    """返回所有命中的 Match 列表"""
    results = []
    
    # 中文
    for pattern in ZH_RUNUPS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            # 建议删除（删除铺垫词）
            results.append(Match(start, end, full_match, ""))
    
    # 英文
    for pattern in EN_RUNUPS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, ""))
    
    return results


def fix(text: str, match_obj: Match) -> str:
    """应用修复：删除铺垫句"""
    if match_obj.suggested_fix:
        return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]
    else:
        return text[:match_obj.start] + text[match_obj.end:]
