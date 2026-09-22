"""
patterns/p14_nominalization.py — Pattern 14: Nominalization

检测：名词化（动词被名词替代）
     - 进行优化 / 做出决定 / 实施改革
修复：改为动词（优化 / 决定 / 改革）
"""

from . import Match
import re
from typing import List

ZH_PATTERNS = [
    (r"进行(?:优化|改进|调整|改革|升级|部署|实施|检查)", lambda m: re.search(r"进行(.+)", m.group()).group(1)),
    (r"做出(?:决定|选择|判断|贡献|努力)", lambda m: re.search(r"做出(.+)", m.group()).group(1)),
    (r"加以(?:考虑|分析|优化|改进)", lambda m: re.search(r"加以(.+)", m.group()).group(1)),
    (r"予以(?:支持|考虑|处理|解决)", lambda m: re.search(r"予以(.+)", m.group()).group(1)),
]

EN_PATTERNS = [
    r"make a (?:decision|choice|determination)",
    r"perform (?:an? )?(?:analysis|evaluation|assessment|optimization)",
    r"conduct (?:an? )?(?:investigation|study|analysis|review)",
    r"implement (?:a |the )?(?:solution|strategy|plan|system)",
    r"provide (?:a |the )?(?:solution|solution|response|answer)",
]

def match(text: str) -> List[Match]:
    results = []
    
    # 中文
    for pattern, fix_fn in ZH_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            try:
                suggested = fix_fn(m)
            except Exception:
                suggested = ""
            results.append(Match(start, end, full_match, suggested))
    
    # 英文
    for pattern in EN_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            # 简化处理：提取核心动词
            suggested = ""  # 纯规则无法准确提取，留空
            results.append(Match(start, end, full_match, suggested))
    
    return results

def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]