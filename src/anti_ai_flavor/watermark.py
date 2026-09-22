#!/usr/bin/env python3
"""
anti_ai_flavor/watermark.py — 文本水印/异常字符检测与清理

覆盖：
- 零宽字符：ZWSP / ZWNJ / ZWJ / BOM
- 同形字异常：全角 ASCII、CJK 兼容字符
- SynthID-Text 采样残留：只做字符分布统计 + 异常提示，不声称删除水印

参考：swaylq/humanize-chinese 的正则集合
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import List


# === 零宽字符 ===
ZW_CHARS = [
    "\u200b",  # ZWSP
    "\u200c",  # ZWNJ
    "\u200d",  # ZWJ
    "\ufeff",  # BOM / ZWNBSP
]

ZW_PATTERN = re.compile("|".join(re.escape(c) for c in ZW_CHARS))


@dataclass
class WatermarkResult:
    cleaned_text: str
    zero_width_removed: int = 0
    homoglyph_replaced: int = 0
    bom_detected: bool = False
    synthid_suspect: bool = False
    synthid_details: str = ""
    warnings: List[str] = field(default_factory=list)


def _remove_zero_width(text: str) -> tuple[str, int, bool]:
    matches = ZW_PATTERN.findall(text)
    count = len(matches)
    bom = "\ufeff" in matches
    cleaned = ZW_PATTERN.sub("", text)
    return cleaned, count, bom


# === 同形字检测 ===
# 全角字母数字（U+FF01–FF5E 中的字母数字子集）→ 半角
# 不动全角标点（，。！？等），避免破坏 golden_set 白名单
_FULLWIDTH_ALNUM_RE = re.compile(r"[\uff21-\uff3a\uff41-\uff5a\uff10-\uff19]")

# CJK 兼容字符（U+F900–FAFF）通常不是正常输入
_CJK_COMPAT_RE = re.compile(r"[\uf900-\ufaff]")

# 常见同形字映射（CJK Compatibility → 常规汉字）
# 只覆盖高频且明显异常的，不扩大化
_HOMOGLYPH_MAP = {
    "Ａ": "A", "Ｂ": "B", "Ｃ": "C", "Ｄ": "D", "Ｅ": "E",
    "Ｆ": "F", "Ｇ": "G", "Ｈ": "H", "Ｉ": "I", "Ｊ": "J",
    "Ｋ": "K", "Ｌ": "L", "Ｍ": "M", "Ｎ": "N", "Ｏ": "O",
    "Ｐ": "P", "Ｑ": "Q", "Ｒ": "R", "Ｓ": "S", "Ｔ": "T",
    "Ｕ": "U", "Ｖ": "V", "Ｗ": "W", "Ｘ": "X", "Ｙ": "Y",
    "Ｚ": "Z",
    "ａ": "a", "ｂ": "b", "ｃ": "c", "ｄ": "d", "ｅ": "e",
    "ｆ": "f", "ｇ": "g", "ｈ": "h", "ｉ": "i", "ｊ": "j",
    "ｋ": "k", "ｌ": "l", "ｍ": "m", "ｎ": "n", "ｏ": "o",
    "ｐ": "p", "ｑ": "q", "ｒ": "r", "ｓ": "s", "ｔ": "t",
    "ｕ": "u", "ｖ": "v", "ｗ": "w", "ｘ": "x", "ｙ": "y",
    "ｚ": "z",
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
}


def _replace_homoglyphs(text: str) -> tuple[str, int]:
    # 全角字母数字 → 半角
    fullwidth_matches = _FULLWIDTH_ALNUM_RE.findall(text)
    text = _FULLWIDTH_ALNUM_RE.sub(
        lambda m: chr(ord(m.group(0)) - 0xFEE0), text
    )
    count = len(fullwidth_matches)

    # 常见同形字映射
    for src, dst in _HOMOGLYPH_MAP.items():
        if src in text:
            text = text.replace(src, dst)
            count += text.count(dst)  # 近似计数

    return text, count


# === SynthID-Text 采样残留检测（只检测，不声称删除） ===
# 思路：SynthID-Text 会对特定 token 分布做绿红list 采样，
# 这里只做简化的字符分布异常提示，不做对抗性重写。

# 检测 CJK 文本中异常的高频同字符重复（SynthID 可能在局部引入非自然重复）
_CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def _check_synthid_suspect(text: str) -> tuple[bool, str]:
    """只返回提示，不修改文本。"""
    cjk_chars = _CJK_CHAR_RE.findall(text)
    if not cjk_chars:
        return False, ""

    total = len(cjk_chars)
    counter = Counter(cjk_chars)
    most_common_char, most_common_count = counter.most_common(1)[0]
    ratio = most_common_count / total

    # 阈值经验值：单字符占比 > 8% 且绝对频次 > 20 时提示
    if ratio > 0.08 and most_common_count > 20:
        return True, (
            f"检测到字符「{most_common_char}」占比 {ratio:.1%}，"
            "可能存在采样水印残留"
        )

    return False, ""


# === 主入口 ===

def detect_watermark(text: str, *, clean: bool = False) -> WatermarkResult:
    """
    检测文本中的水印/异常字符。

    clean=False（默认）：只检测，不改动文本。
    clean=True：移除零宽字符 + 替换同形字，但不声称删除 SynthID。
    """
    warnings: List[str] = []
    zero_width_removed = 0
    bom_detected = False
    homoglyph_replaced = 0
    cleaned_text = text

    if clean:
        cleaned_text, zero_width_removed, bom_detected = _remove_zero_width(text)
        if bom_detected:
            warnings.append("检测到 BOM (U+FEFF)，已移除")
        if zero_width_removed:
            warnings.append(f"移除 {zero_width_removed} 个零宽字符")

        cleaned_text, homoglyph_replaced = _replace_homoglyphs(cleaned_text)
        if homoglyph_replaced:
            warnings.append(f"替换 {homoglyph_replaced} 处同形字/全角字符")
    else:
        # 只检测
        zw_matches = ZW_PATTERN.findall(text)
        zero_width_removed = len(zw_matches)
        if zero_width_removed:
            warnings.append(f"检测到 {zero_width_removed} 个零宽字符")
        if "\ufeff" in zw_matches:
            bom_detected = True
            warnings.append("检测到 BOM (U+FEFF)")

        fullwidth_count = len(_FULLWIDTH_ALNUM_RE.findall(text))
        compat_count = len(_CJK_COMPAT_RE.findall(text))
        if fullwidth_count:
            warnings.append(f"检测到 {fullwidth_count} 个全角 ASCII 字符")
        if compat_count:
            warnings.append(f"检测到 {compat_count} 个 CJK 兼容字符")

    # Synthid 提示（无论 clean 与否）
    suspect, detail = _check_synthid_suspect(text)
    if suspect:
        warnings.append("Synthid-Text 采样残留提示：" + detail)

    return WatermarkResult(
        cleaned_text=cleaned_text,
        zero_width_removed=zero_width_removed,
        homoglyph_replaced=homoglyph_replaced,
        bom_detected=bom_detected,
        synthid_suspect=suspect,
        synthid_details=detail,
        warnings=warnings,
    )
