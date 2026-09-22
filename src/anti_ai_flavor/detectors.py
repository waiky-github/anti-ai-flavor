"""
anti_ai_flavor/detectors.py — 文本检测器（只读，不改写）

提供 tier1 / symmetry / mechanical / summary_closer / abstract / idiom / em_dash 等检测。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .rules import (
    TIER1_ZH,
    TIER1_EN,
    SYMMETRY_FILLERS,
    SYMMETRY_FILLERS_EN,
    MECHANICAL_ORDERING,
    SUMMARY_CLOSERS,
    ABSTRACT_SUBJECTS,
    IDIOM_FILLERS,
    EM_DASH_OVERUSE,
)


def detect_tier1(text: str) -> list:
    """检测 Tier 1 词，返回 [(词, 位置描述)]"""
    hits = []
    for word in TIER1_ZH + TIER1_EN:
        if word in text:
            idx = text.find(word)
            line_num = text[:idx].count("\n") + 1
            hits.append((word, f"第 {line_num} 行"))
    return hits


def detect_symmetry(text: str) -> list:
    """检测对称填充（中文 + 英文）"""
    hits = []
    for pattern in SYMMETRY_FILLERS:
        matches = re.findall(pattern, text)
        if matches:
            hits.append(f"对称填充: {matches[0][:50]}...")
    for pattern in SYMMETRY_FILLERS_EN:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            hits.append(f"对称填充(EN): {matches[0][:50]}...")
    # 检测跨句 not only...but also / not only...is also（C05 类，rewrite 白名单外仍应被检出）
    cross_sentence = re.findall(
        r"not only\s+[\s\S]*?\s+(?:but also|is also)\s+[\s\S]*?[.!?]",
        text,
        re.IGNORECASE,
    )
    for m in cross_sentence:
        hits.append(f"对称填充(EN-跨句): {m[:50]}...")
    return hits


def detect_mechanical(text: str) -> list:
    """检测机械排序"""
    hits = []
    for pattern in MECHANICAL_ORDERING:
        if re.search(pattern, text):
            hits.append(f"机械排序: {pattern}")
    return hits


def detect_summary_closer(text: str) -> list:
    """检测总结性结尾"""
    hits = []
    for pattern in SUMMARY_CLOSERS:
        matches = re.findall(pattern, text)
        if matches:
            hits.append(f"总结性结尾: {matches[0][:50]}...")
    return hits


def detect_abstract(text: str) -> list:
    """检测抽象主语"""
    hits = []
    for pattern in ABSTRACT_SUBJECTS:
        matches = re.findall(pattern, text)
        if matches:
            hits.append(f"抽象主语: {matches[0][:50]}...")
    return hits


def detect_idiom(text: str) -> list:
    """检测成语 filler"""
    hits = []
    for idiom in IDIOM_FILLERS:
        if idiom in text:
            hits.append(f"成语 filler: {idiom}")
    return hits


def detect_em_dash(text: str) -> list:
    """检测破折号过度使用"""
    if re.search(EM_DASH_OVERUSE, text):
        return ["破折号过度使用（连续 2 个以上）"]
    return []


def detect_all(text: str) -> dict:
    """执行全量检测"""
    return {
        "tier1": detect_tier1(text),
        "symmetry": detect_symmetry(text),
        "mechanical": detect_mechanical(text),
        "summary_closer": detect_summary_closer(text),
        "abstract": detect_abstract(text),
        "idiom": detect_idiom(text),
        "em_dash": detect_em_dash(text),
    }


def severity(detections: dict) -> str:
    """评估严重程度"""
    total = sum(len(v) for v in detections.values())
    if total == 0:
        return "无大碍"
    elif total <= 2:
        return "轻改"
    else:
        return "重写"


__all__ = [
    "detect_tier1",
    "detect_symmetry",
    "detect_mechanical",
    "detect_summary_closer",
    "detect_abstract",
    "detect_idiom",
    "detect_em_dash",
    "detect_all",
    "severity",
]
