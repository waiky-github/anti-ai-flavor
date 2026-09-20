"""
patterns/p20_stilted_coordination.py — Pattern 20: Stilted coordination

检测：生硬并列结构
     - 既...又...（过度使用）
     - both...and...
修复：简化或删除其中一个并列项
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class Match:
    start: int
    end: int
    matched_text: str
    suggested_fix: str  # "" 表示简化处理


ZH_PATTERNS = [
    r"既[^，,。]*?[，,][\s]*又",
    r"既[^，,。]*?[，,][\s]*而且",
    r"不仅[^，,。]*?[，,][\s]*而且",
    r"不仅[^，,。]*?[，,][\s]*也",
    r"不但[^，,。]*?[，,][\s]*而且",
    r"不但[^，,。]*?[，,][\s]*也",
]

EN_PATTERNS = [
    r"both\s+[^,]+?\s+and\s+",
    r"not only\s+[^,]+?\s+but also\s+",
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
            # 找到连接词位置，用于提取保留内容
            connector_match = re.search(r'(也|而且|又)', full_match)
            if connector_match:
                # 找到前缀（不仅/不但/既）的结束位置
                prefix_match = re.match(r'(不仅|不但|既)', full_match)
                if prefix_match:
                    keep_start = prefix_match.end()
                else:
                    keep_start = 0
                keep_end = connector_match.start()
                after_connector = connector_match.end()
                # 保留：前缀后到连接词前 + 连接词后到结尾
                suggested = full_match[keep_start:keep_end] + full_match[after_connector:]
                suggested = suggested.strip("，, ")
            else:
                suggested = ""
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
            # 保留 not only 和 but also 之间的内容 + but also 后面的内容，用 and 连接
            not_only_match = re.search(r'\bnot\s+only\b', full_match, re.IGNORECASE)
            but_also_match = re.search(r'\bbut\s+also\b', full_match, re.IGNORECASE)
            but_match = re.search(r'\bbut\b(?!\s+also)', full_match, re.IGNORECASE)
            if not_only_match and (but_also_match or but_match):
                if but_also_match:
                    # not only X but also Y -> X and Y
                    between = full_match[not_only_match.end():but_also_match.start()].strip()
                    after = full_match[but_also_match.end():].strip()
                    suggested = f"{between} and {after}" if between and after else (between or after)
                elif but_match:
                    # not only X but Y -> X and Y
                    between = full_match[not_only_match.end():but_match.start()].strip()
                    after = full_match[but_match.end():].strip()
                    suggested = f"{between} and {after}" if between and after else (between or after)
                else:
                    suggested = ""
            else:
                suggested = ""
            results.append(Match(start, end, full_match, suggested))
    
    return results


def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]
