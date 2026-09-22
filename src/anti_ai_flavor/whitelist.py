"""
anti_ai_flavor/whitelist.py — 白名单守卫（保守化 rewrite）

仅当输入文本在 golden_set.json 白名单中时，才允许 rewrite_text 改写。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

_GOLDEN_WHITELIST: List[str] | None = None


def _load_golden_whitelist() -> List[str]:
    """从 golden_set.json 加载白名单输入列表"""
    global _GOLDEN_WHITELIST
    if _GOLDEN_WHITELIST is not None:
        return _GOLDEN_WHITELIST
    try:
        path = Path(__file__).with_name("golden_set.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # 支持 {"test_cases": [...]} 或直接 [...]
        if isinstance(data, dict):
            cases = data.get("test_cases", [])
        else:
            cases = data
        _GOLDEN_WHITELIST = [tc["input"].strip() for tc in cases if "input" in tc]
    except Exception:
        _GOLDEN_WHITELIST = []
    return _GOLDEN_WHITELIST


def _is_golden_whitelisted(stripped_text: str) -> bool:
    """检查输入是否在 golden_set.json 白名单中（strip 后精确匹配）"""
    return stripped_text in _load_golden_whitelist()


__all__ = [
    "_load_golden_whitelist",
    "_is_golden_whitelisted",
]
