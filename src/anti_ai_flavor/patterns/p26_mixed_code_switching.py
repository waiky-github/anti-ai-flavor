"""
patterns/p26_mixed_code_switching.py — Pattern 26: Mixed code-switching

检测：中英混杂句式（英文主语/指示词 + 中文谓语正文）
     - The system 能够显著提升效率
     - This 不仅提升了效率
修复：删除英文前缀，保留中文主体
"""

from . import Match
import re
from typing import List


ZH_PATTERNS = [
    r"(?:The system|This|That)\s+[^。]*?[。！]",
]

EN_PATTERNS = []


def match(text: str) -> List[Match]:
    results = []

    for pattern in ZH_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = m.start()
            end = m.end()
            full_match = text[start:end]
            # suggested_fix: 将英文前缀替换为中文「系统」
            # e.g. "The system 能够..." -> "系统能够..."
            suggested_fix = re.sub(r"^(?:The system|This|That)\s+", "系统", full_match, flags=re.IGNORECASE)
            results.append(Match(start, end, full_match, suggested_fix))

    return results


def fix(text: str, match_obj: Match) -> str:
    return text[:match_obj.start] + match_obj.suggested_fix + text[match_obj.end:]
