"""
patterns/p02_one_line_closer.py — Pattern 2: One-line closer

检测：段落结尾的短总结句/感叹句
     - 这就是真正的价值
     - 这才是最重要的
     - 意义重大
修复：删除或合并到前一句
"""

from . import Match
import re
from typing import List

# 中文总结性结尾词（短句）
ZH_CLOSERS = [
    r"这就是真正的价值",
    r"这才是最重要的",
    r"意义重大",
    r"这才是关键",
    r"这才是重点",
    r"这才是核心",
    r"这才是本质",
    r"这才是根本",
    r"这才是目的",
    r"这才是意义",
]

# 英文总结性结尾词（短句）
EN_CLOSERS = [
    r"This is what really matters",
    r"This is the real value",
    r"This is the key point",
    r"This is what it's all about",
    r"This is the bottom line",
]

def match(text: str) -> List[Match]:
    """返回所有命中的 Match 列表"""
    results = []
    
    # 中文
    for pattern in ZH_CLOSERS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            # 建议删除（整句删除）
            results.append(Match(start, end, full_match, ""))
    
    # 英文
    for pattern in EN_CLOSERS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            results.append(Match(start, end, full_match, ""))
    
    return results

def fix(text: str, match_obj: Match) -> str:
    """应用修复：删除总结句"""
    if match_obj.suggested_fix:
        # 保留建议内容
        return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]
    else:
        # 删除整句
        return text[:match_obj.start] + text[match_obj.end:]