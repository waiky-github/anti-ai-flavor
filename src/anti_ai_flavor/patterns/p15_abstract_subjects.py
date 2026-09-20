"""
patterns/p15_abstract_subjects.py — Pattern 15: Abstract subjects

检测：抽象主语
     - 该技术的应用
     - the implementation of
     - 这一举措
修复：改为具体主语（纯规则只能删除，无法自动改为具体主语）
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class Match:
    start: int
    end: int
    matched_text: str
    suggested_fix: str  # "" 表示删除


ZH_PATTERNS = [
    r"该技术的应用",
    r"该技术的实现",
    r"这一举措",
    r"该方案的实施",
    r"本项目",
    r"该系统的建设",
    r"这一过程",
    r"上述(?:分析|研究|工作)",
]

EN_PATTERNS = [
    r"the implementation of",
    r"the application of",
    r"the utilization of",
    r"the deployment of",
    r"the development of",
    r"this initiative",
    r"the aforementioned",
    r"the aforementioned (?:study|research|work|analysis)",
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
