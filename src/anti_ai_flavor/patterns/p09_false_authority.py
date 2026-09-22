"""
patterns/p09_false_authority.py — Pattern 9: False authority

检测：虚假权威（无引用的专家/研究声称）
     - 专家表示
     - studies show
     - 据调查
修复：删除或标记为需要引用
"""

from . import Match
import re
from typing import List


ZH_PATTERNS = [
    r"专家(?:表示|认为|指出)",
    r"据(?:调查|研究|统计)",
    r"研究表明",
    r"调查显示",
    r"数据显示",
    r"有(?:人|专家)指出",
    r"据(?:专家|权威)透露",
]

EN_PATTERNS = [
    r"studies show",
    r"research shows",
    r"experts say",
    r"experts believe",
    r"it is said that",
    r"according to (?:a |the )?(?:study|research|survey)",
    r"statistics show",
    r"data shows",
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