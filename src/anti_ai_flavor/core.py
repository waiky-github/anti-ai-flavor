#!/usr/bin/env python3
"""
anti_ai_flavor/core.py — 中文去 AI 味核心逻辑

独立包入口，不依赖 Hermes。
"""

import re
import sys
from pathlib import Path

# === Phase 1：25-pattern 体系 ===
try:
    from .patterns import TIER1_ZH as LEGACY_TIER1_ZH, TIER1_EN as LEGACY_TIER1_EN
    from .patterns.p01_not_x_but_y import match as p01_match, fix as p01_fix
    from .patterns.p02_one_line_closer import match as p02_match, fix as p02_fix
    from .patterns.p03_staged_runup import match as p03_match, fix as p03_fix
    from .patterns.p04_arguing_no_one import match as p04_match, fix as p04_fix
    from .patterns.p05_forced_triads import match as p05_match, fix as p05_fix
    from .patterns.p06_undue_caution import match as p06_match, fix as p06_fix
    from .patterns.p07_artificial_imbalance import match as p07_match, fix as p07_fix
    from .patterns.p08_meta_commentary import match as p08_match, fix as p08_fix
    from .patterns.p09_false_authority import match as p09_match, fix as p09_fix
    from .patterns.p10_list_fatigue import match as p10_match, fix as p10_fix
    from .patterns.p11_rhetorical_questions import match as p11_match, fix as p11_fix
    from .patterns.p12_excessive_transitions import match as p12_match, fix as p12_fix
    from .patterns.p13_passive_overuse import match as p13_match, fix as p13_fix
    from .patterns.p14_nominalization import match as p14_match, fix as p14_fix
    from .patterns.p15_abstract_subjects import match as p15_match, fix as p15_fix
    from .patterns.p16_formulaic_closers import match as p16_match, fix as p16_fix
    from .patterns.p17_forced_formality import match as p17_match, fix as p17_fix
    from .patterns.p18_repetition_rhythm import match as p18_match, fix as p18_fix
    from .patterns.p19_over_qualification import match as p19_match, fix as p19_fix
    from .patterns.p20_stilted_coordination import match as p20_match, fix as p20_fix
    from .patterns.p21_unnecessary_clarifications import match as p21_match, fix as p21_fix
    from .patterns.p22_over_structuring import match as p22_match, fix as p22_fix
    from .patterns.p23_false_precision import match as p23_match, fix as p23_fix
    from .patterns.p24_moralizing import match as p24_match, fix as p24_fix
    from .patterns.p25_vagueness_by_design import match as p25_match, fix as p25_fix
    from .patterns.p26_mixed_code_switching import match as p26_match, fix as p26_fix
    PATTERNS_AVAILABLE = True
except ImportError:
    PATTERNS_AVAILABLE = False

# === Phase 2：LLM 检测器（可选） ===
try:
    from .llm_detector import create_detector
    LLM_DETECTOR_AVAILABLE = True
except ImportError:
    LLM_DETECTOR_AVAILABLE = False

# === Legacy 词表（统一数据源） ===
from .rules import (
    TIER1_ZH,
    TIER1_EN,
    IDIOM_FILLERS,
    DENSITY_FILLERS,
    REDUNDANT_MODIFIERS,
    SYMMETRY_FILLERS_EN,
    ABSTRACT_SUBJECTS_EN,
    FIXED_CONNECTORS_EN,
    SUMMARY_CLOSERS_EN,
    SYMMETRY_FILLERS,
    MECHANICAL_ORDERING,
    SUMMARY_CLOSERS,
    ABSTRACT_SUBJECTS,
    EM_DASH_OVERUSE,
)

# === 检测器（只读，不改写） ===
from .detectors import (
    detect_tier1,
    detect_symmetry,
    detect_mechanical,
    detect_summary_closer,
    detect_abstract,
    detect_idiom,
    detect_em_dash,
    detect_all,
    severity,
)

# === 白名单守卫 ===
from .whitelist import _is_golden_whitelisted

# === Phase 1：25-pattern 体系核心函数 ===

def _rewrite_with_patterns(text: str, scene: str = "default") -> str:
    """
    使用 25-pattern 体系重写文本。
    
    流程：
      1. 应用 pattern 1-4（强 pattern，直接修复）
      2. 应用 pattern 5（标记，不强制修改）
      3. 应用 pattern 6-10（高优先级 pattern）
      4. 应用 pattern 11-16（中优先级 pattern）
      5. 应用 pattern 17-25（低优先级 pattern，部分标记不修改）
      6. 删除 Tier 1 词（补充 legacy 规则）
      7. 清理残留（标点、空格、短句）
    """
    if not PATTERNS_AVAILABLE:
        # fallback 到原有逻辑
        return _legacy_rewrite(text, scene)
    
    original_text = text
    
    # === 第一步：应用强 pattern（1-4） ===
    pattern_fixes = [
        (p01_match, p01_fix),   # Not X but Y
        (p02_match, p02_fix),   # One-line closer
        (p03_match, p03_fix),   # Staged run-up
        (p04_match, p04_fix),   # Arguing with no one
    ]
    
    for match_fn, fix_fn in pattern_fixes:
        matches = match_fn(text)
        if matches:
            # 从后往前替换，避免位置偏移
            for m in reversed(matches):
                text = fix_fn(text, m)
    
    # === 第二步：应用 pattern 5（标记，不修改） ===
    _ = p05_match(text)  # 只检测，不修改
    
    # === 第三步：应用 pattern 6-10（高优先级，直接修复） ===
    pattern_fixes_p6_10 = [
        (p06_match, p06_fix),   # Undue caution
        (p07_match, p07_fix),   # Artificial imbalance
        (p08_match, p08_fix),   # Meta-commentary
        (p09_match, p09_fix),   # False authority
        (p10_match, p10_fix),   # List fatigue
    ]
    
    for match_fn, fix_fn in pattern_fixes_p6_10:
        matches = match_fn(text)
        if matches:
            for m in reversed(matches):
                text = fix_fn(text, m)
    
    # === 第四步：应用 pattern 11-16（中优先级，直接修复） ===
    pattern_fixes_p11_16 = [
        (p11_match, p11_fix),   # Rhetorical questions
        (p12_match, p12_fix),   # Excessive transitions
        (p13_match, p13_fix),   # Passive overuse
        (p14_match, p14_fix),   # Nominalization
        (p15_match, p15_fix),   # Abstract subjects
        (p16_match, p16_fix),   # Formulaic closers
    ]
    
    for match_fn, fix_fn in pattern_fixes_p11_16:
        matches = match_fn(text)
        if matches:
            for m in reversed(matches):
                text = fix_fn(text, m)
    
    # === 第五步：应用 pattern 17-25（低优先级，部分标记不修改） ===
    # 这些 pattern 的 fix 函数可能返回空字符串（表示标记但不修改）
    pattern_fixes_p17_25 = [
        (p17_match, p17_fix),   # Forced formality
        (p18_match, p18_fix),   # Repetition for rhythm
        (p19_match, p19_fix),   # Over-qualification
        (p20_match, p20_fix),   # Stilted coordination
        (p21_match, p21_fix),   # Unnecessary clarifications
        (p22_match, p22_fix),   # Over-structuring
        (p23_match, p23_fix),   # False precision
        (p24_match, p24_fix),   # Moralizing
        (p25_match, p25_fix),   # Vagueness by design
        (p26_match, p26_fix),   # Mixed code-switching
    ]
    
    for match_fn, fix_fn in pattern_fixes_p17_25:
        matches = match_fn(text)
        if matches:
            for m in reversed(matches):
                fixed = fix_fn(text, m)
                # 只应用非空修复（空字符串表示标记但不修改）
                if fixed != text:
                    text = fixed
    
    # === 第六步：删除 Tier 1 词 + 机械排序/对称填充/总结结尾/抽象主语（补充 legacy 规则） ===
    for word in LEGACY_TIER1_ZH + LEGACY_TIER1_EN:
        if any('\u4e00' <= c <= '\u9fff' for c in word):
            text = text.replace(word, "")
        else:
            base = word.rstrip('.,;:!?')
            pattern = re.compile(re.escape(base), re.IGNORECASE)
            text = pattern.sub("", text)

    # 删除机械排序词（首先/其次/最后/First/Second/Finally）
    for pattern_str in MECHANICAL_ORDERING:
        text = re.sub(pattern_str, "", text)

    # 删除对称填充（一方面...另一方面/既...又/不仅...而且/虽然...但...）
    # 保留尾段，删除连接词
    for pattern_str in SYMMETRY_FILLERS:
        matches = list(re.finditer(pattern_str, text, re.IGNORECASE))
        for m in reversed(matches):
            start_m = m.start()
            end_m = m.end()
            full_match = m.group()
            
            if "，" in full_match:
                parts = full_match.split("，")
                if len(parts) >= 2:
                    keep_part = parts[-1]
                    for connector in ["另一方面", "不仅", "而且", "但", "既", "又"]:
                        keep_part = keep_part.replace(connector, "").strip()
                    keep_part = keep_part.strip("，。").strip()
                    if keep_part:
                        text = text[:start_m] + keep_part + text[end_m:]
                    else:
                        text = text[:start_m] + text[end_m:]
            else:
                text = text[:start_m] + text[end_m:]

    # 删除英文对称填充（not only...but also/both...and/On one hand...）
    # 保留尾段，删除连接词
    for pattern_str in SYMMETRY_FILLERS_EN:
        matches = list(re.finditer(pattern_str, text, re.IGNORECASE))
        for m in reversed(matches):
            start_m = m.start()
            end_m = m.end()
            full_match = m.group()
            
            # 对于 On one hand...on the other hand...，保留两个信息点
            if "on the other hand" in full_match.lower():
                # 找到 on the other hand 的位置
                other_hand_match = re.search(r'on\s+the\s+other\s+hand', full_match, re.IGNORECASE)
                if other_hand_match:
                    # 第一部分：On one hand 之后到 on the other hand 之前
                    part1 = full_match[:other_hand_match.start()].strip()
                    # 第二部分：on the other hand 之后
                    part2 = full_match[other_hand_match.end():].strip()
                    
                    # 删前缀
                    part1 = re.sub(r'^on\s+one\s+hand\s*[,.]?\s*', '', part1, flags=re.IGNORECASE).strip()
                    part2 = re.sub(r'^on\s+the\s+other\s+hand\s*[,.]?\s*', '', part2, flags=re.IGNORECASE).strip()
                    
                    # 删前缀标点
                    part1 = re.sub(r'^[，,。.\s]+', '', part1).strip()
                    part2 = re.sub(r'^[，,。.\s]+', '', part2).strip()
                    
                    # 合并
                    keep_parts = []
                    if part1:
                        keep_parts.append(part1)
                    if part2:
                        keep_parts.append(part2)
                    
                    keep_part = ' '.join(keep_parts)
                    if keep_part:
                        text = text[:start_m] + keep_part + text[end_m:]
                    else:
                        text = text[:start_m] + text[end_m:]
                else:
                    text = text[:start_m] + text[end_m:]
            # 对于 not only...but also / both...and，保留 but also / and 后面的内容
            elif "but also" in full_match.lower() or "and" in full_match.lower():
                # 找到 but also / and 的位置
                but_also_match = re.search(r'but\s+also', full_match, re.IGNORECASE)
                and_match = re.search(r'\band\b', full_match, re.IGNORECASE)
                if but_also_match:
                    keep_start = start_m + but_also_match.end()
                elif and_match:
                    keep_start = start_m + and_match.end()
                else:
                    keep_start = end_m
                keep_part = text[keep_start:end_m].strip()
                # 删除前面的逗号/句号
                keep_part = re.sub(r'^[，,。.\s]+', '', keep_part).strip()
                if keep_part:
                    text = text[:start_m] + keep_part + text[end_m:]
                else:
                    text = text[:start_m] + text[end_m:]
            else:
                text = text[:start_m] + text[end_m:]
    
    # 删除 not only...but also 跨句病句（C05），保留 but also 后面的内容
    text = re.sub(
        r'not only\s+[\s\S]*?\s+but also\s+[\s\S]*?[.!?]',
        lambda m: m.group().split('but also')[-1].strip(),
        text,
        flags=re.IGNORECASE
    )
    # 处理 not only...also 跨句结构（C05 变体），保留 also 后面的内容
    text = re.sub(
        r'not only\s+[\s\S]*?\s+also\s+[\s\S]*?[.!?]',
        lambda m: m.group().split('also')[-1].strip(),
        text,
        flags=re.IGNORECASE
    )

    # 删除总结性结尾
    for pattern_str in SUMMARY_CLOSERS:
        text = re.sub(pattern_str, "", text)
    for pattern_str in SUMMARY_CLOSERS_EN:
        text = re.sub(pattern_str, "", text)

    # 删除抽象主语
    for pattern_str in ABSTRACT_SUBJECTS:
        text = re.sub(pattern_str, "", text)
    for pattern_str in ABSTRACT_SUBJECTS_EN:
        text = re.sub(pattern_str, "", text)

    # 删除英文固定衔接词
    for pattern_str in FIXED_CONNECTORS_EN:
        text = re.sub(pattern_str, "", text)

    # 删除成语 filler
    for idiom in IDIOM_FILLERS:
        text = text.replace(idiom, "")

    # 删除密度填充（在当今.../随着...发展/势在必行/必然选择）
    for pattern_str in DENSITY_FILLERS:
        text = re.sub(pattern_str, "", text)

    # 删除冗余修饰词（系统性的/全面的/整体的等）
    for pattern_str in REDUNDANT_MODIFIERS:
        text = re.sub(pattern_str, "", text)

    # === 第六点五步：机械排序残留 cleanup ===
    # 把机械排序删除后的"。，"
    text = re.sub(r"。，", "，", text)
    # 删除中文分句中冗余主语
    text = re.sub(r"，我们要", "，", text)
    text = re.sub(r"，开始", "，", text)
    text = re.sub(r"我们开始", "", text)
    text = re.sub(r"然后我们开始", "", text)
    # 删除英文分句中 p10 遗留的冗余主语（中间位置，保留第一个 we need to）
    text = re.sub(r"\s*,\s*we should", "", text)
    text = re.sub(r"\s*,\s*we can", "", text)
    
    # === 第七步：清理残留 ===
    text = _cleanup_residue(text)
    
    # === 第八步：合并句子 ===
    text = _merge_sentences(text)
    
    # === 第九步：最终清理 ===
    text = _final_cleanup(text)
    
    return text.strip()




def _cleanup_residue(text: str) -> str:
    """清理 pattern 删除后的残留"""
    # 清理标点残留
    text = re.sub(r"，{2,}", "，", text)
    text = re.sub(r"。{2,}", "。", text)
    text = re.sub(r"…{2,}", "…", text)
    text = re.sub(r"[\s]+", " ", text)
    
    # 删除开头的标点
    text = re.sub(r"^[，,。！？\s]+", "", text)
    
    # 删除孤立的"是"（前面没有汉字或数字）
    text = re.sub(r"(?<![a-zA-Z0-9\u4e00-\u9fff])是(?![a-zA-Z0-9\u4e00-\u9fff])", "", text)
    # 删除孤立的"的"
    text = re.sub(r"(?<![a-zA-Z0-9\u4e00-\u9fff])的(?![a-zA-Z0-9\u4e00-\u9fff])", "", text)
    # 删除"的、"残留
    text = re.sub(r"的、", "的", text)
    # 删「系统性的」→「系统性」（只删「的」后缀，保留修饰词）
    text = re.sub(r"(?<=系统性)的", "", text)
    # 删「全面的」→「全面」（只删「的」后缀，保留修饰词）
    text = re.sub(r"(?<=全面)的", "", text)
    # 删除"、"残留（前后无汉字/字母/数字）
    text = re.sub(r"(?<![a-zA-Z0-9\u4e00-\u9fff])、", "", text)
    text = re.sub(r"、(?!([a-zA-Z0-9\u4e00-\u9fff]))", "", text)
    # 删除"、"与"的"连用的冗余残留
    text = re.sub(r"、的", "", text)
    # 删除逗号残留
    text = re.sub(r"(?<![a-zA-Z0-9\u4e00-\u9fff])，(?![a-zA-Z0-9\u4e00-\u9fff])", "", text)
    
    return text


def _merge_sentences(text: str) -> str:
    """合并句子，确保句子间有空格"""
    # 按句号/问号/感叹号分句（中英文）
    sentences = re.split(r'(?<=[。！？.!?\n])', text)
    rewritten = []
    for sent in sentences:
        sent = sent.strip()
        # 删除句首残留的逗号（p10 等 pattern 遗留）
        sent = re.sub(r'^[，,]\s*', '', sent).strip()
        if sent:
            rewritten.append(sent)
    
    # 合并句子，确保句子间有空格
    result = " ".join(rewritten)
    
    # 删除标点前的空格
    result = re.sub(r" ([，。！？.!?])", r"\1", result)
    
    # === 英文 staged runup 合并（在整个 result 中搜索，不仅限于开头） ===
    # 三段: We need to X. Y. Z
    staged_runup_3 = re.compile(
        r'\b(We need to .*?)[.]\s*(\w.+?)[.]\s*(.+?)(?=[.]|$)',
        re.IGNORECASE
    )
    # 两段: We need to X. Y
    staged_runup_2 = re.compile(
        r'\b(We need to .*?)[.]\s*(\w.+?)(?=[.]|$)',
        re.IGNORECASE
    )
    
    # 从后往前替换，避免位置偏移
    for pattern in [staged_runup_3, staged_runup_2]:
        matches = list(pattern.finditer(result))
        for m in reversed(matches):
            if pattern == staged_runup_3:
                first = m.group(1).strip()
                if first and first[0].islower():
                    first = first[0].upper() + first[1:]
                second = m.group(2).strip()
                third = m.group(3).strip()
                # 移除 "We should" / "We can" / "We" 主语
                second = re.sub(r'^(?:We should|We can|We)\s+', '', second, flags=re.IGNORECASE).strip()
                third = re.sub(r'^(?:We should|We can|We)\s+', '', third, flags=re.IGNORECASE).strip()
                # 如果 third 是动词短语，加 "then"
                if third and not third.lower().startswith('then'):
                    third = 'then ' + third
                replacement = f"{first}, {second}, {third}."
            else:
                first = m.group(1).strip()
                if first and first[0].islower():
                    first = first[0].upper() + first[1:]
                second = m.group(2).strip()
                # 移除 "We should" / "We can" / "We" 主语
                second = re.sub(r'^(?:We should|We can|We)\s+', '', second, flags=re.IGNORECASE).strip()
                # 如果 second 是动词短语，加 "then"
                if second and not second.lower().startswith('then'):
                    second = 'then ' + second
                replacement = f"{first}, {second}."
            # 清理前后空格，避免重复句号
            before = result[:m.start()].rstrip()
            after = result[m.end():]
            if after.startswith('.') and replacement.endswith('.'):
                after = after[1:]
            separator = '' if before.endswith('。') else ' '
            result = before + separator + replacement + after
    
    return result


def _final_cleanup(text: str) -> str:
    """最终清理"""
    # 中英文之间加空格（如果缺失）
    text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2', text)
    
    # 清理连续句号（不插入空格，不删结尾句号）
    text = re.sub(r'[。]{2,}', '。', text)
    text = re.sub(r'[.]{2,}', '.', text)
    
    # 删除开头的标点
    text = re.sub(r'^[，,。！？\s]+', '', text)
    
    return text



def _legacy_rewrite(text: str, scene: str = "default") -> str:
    """原有 rewrite 逻辑（fallback）"""
    # 预处理：统一分号为逗号，方便 symmetry 跨句匹配
    text = text.replace("；", "，")
    
    # 先处理中文对称填充（跨句，大小写不敏感）
    for pattern in SYMMETRY_FILLERS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        for m in reversed(matches):
            start_m = m.start()
            end_m = m.end()
            full_match = m.group()
            
            if "，" in full_match:
                parts = full_match.split("，")
                if len(parts) >= 2:
                    keep_part = parts[-1]
                    for connector in ["另一方面", "不仅", "而且"]:
                        keep_part = keep_part.replace(connector, "").strip()
                    keep_part = keep_part.strip("，。").strip()
                    if keep_part:
                        text = text[:start_m] + keep_part + text[end_m:]
                    else:
                        text = text[:start_m] + text[end_m:]
            else:
                text = text[:start_m] + text[end_m:]
    
    # 先处理英文对称填充（跨句，大小写不敏感）
    for pattern in SYMMETRY_FILLERS_EN:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        for m in reversed(matches):
            start_m = m.start()
            end_m = m.end()
            full_match = m.group()
            # 按逗号或分号分割
            if "," in full_match or ";" in full_match:
                parts = re.split(r'[,;]', full_match)
                if len(parts) >= 2:
                    keep_part = parts[-1]
                    for connector in ["on the other hand", "but also"]:
                        keep_part = keep_part.replace(connector, "").strip()
                    keep_part = keep_part.strip(",.").strip()
                    if keep_part:
                        text = text[:start_m] + keep_part + text[end_m:]
                    else:
                        text = text[:start_m] + text[end_m:]
    
    # 现在分句（按句号/问号/感叹号）
    sentences = re.split(r'(?<=[。！？\n])', text)
    
    rewritten_sentences = []
    for sent in sentences:
        if not sent.strip():
            continue
            
        result = sent.strip()
        
        # 删除总结性结尾（整句匹配）
        for pattern in SUMMARY_CLOSERS:
            result = re.sub(pattern, "", result)
        
        # 删除英文总结性结尾
        for pattern in SUMMARY_CLOSERS_EN:
            result = re.sub(pattern, "", result)
        
        # 删除抽象主语
        for pattern in ABSTRACT_SUBJECTS:
            result = re.sub(pattern, "", result)
        
        # 删除英文抽象主语（大小写不敏感）
        for pattern in ABSTRACT_SUBJECTS_EN:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        # 删除机械排序词
        for pattern in MECHANICAL_ORDERING:
            result = re.sub(pattern, "", result)
        
        # 删除英文固定衔接词（大小写不敏感）
        for pattern in FIXED_CONNECTORS_EN:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        # 删除 Tier 1 词（大小写不敏感）
        for word in TIER1_ZH + TIER1_EN:
            # 中文直接替换
            if any('\u4e00' <= c <= '\u9fff' for c in word):
                result = result.replace(word, "")
            else:
                # 英文大小写不敏感替换
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                result = pattern.sub("", result)
        
        # 删除成语 filler
        for idiom in IDIOM_FILLERS:
            result = result.replace(idiom, "")
        
        # 清理破折号过度使用
        result = re.sub(r"——\s*——", "——", result)
        
        # 清理标点残留
        result = re.sub(r"，{2,}", "，", result)
        result = re.sub(r"。{2,}", "。", result)
        result = re.sub(r"…{2,}", "…", result)
        result = re.sub(r"[\s]+", " ", result)
        
        result = re.sub(r"^[，,。！？\\s]+", "", result)
        result = re.sub(r"[，,。！？\\s]+$", "", result)
        # 删除孤立的"是"
        result = re.sub(r"(?<![a-zA-Z0-9\\u4e00-\\u9fff])是(?![a-zA-Z0-9\\u4e00-\\u9fff])", "", result)
        # 删除孤立的"的"
        result = re.sub(r"(?<![a-zA-Z0-9\\u4e00-\\u9fff])的(?![a-zA-Z0-9\\u4e00-\\u9fff])", "", result)
        # 删除逗号残留
        result = re.sub(r"(?<![a-zA-Z0-9\\u4e00-\\u9fff])，(?![a-zA-Z0-9\\u4e00-\\u9fff])", "", result)
        
        # 删除过短句子（少于 3 个汉字，可能是残留）
        def is_short_chinese(s):
            chinese_chars = re.findall(r'[\u4e00-\u9fff]', s)
            return len(chinese_chars) < 3
        
        if result and not is_short_chinese(result):
            rewritten_sentences.append(result)
        elif result and re.search(r'[a-zA-Z0-9]', result):
            # 保留包含英文/数字的句子
            rewritten_sentences.append(result)
        elif result and len(result.strip()) > 0:
            # 保留其他非空句子（避免全部删除）
            rewritten_sentences.append(result)
    
    # 合并句子
    result = " ".join(rewritten_sentences)
    result = re.sub(r" ([，。！？])", r"\1", result)  # 删除标点前的空格
    
    # 最终清理
    result = re.sub(r"。([^。\n])", "。\1", result)
    
    # 中英文之间加空格（如果缺失）
    result = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2', result)
    result = re.sub(r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2', result)
    
    # 清理句号残留
    result = re.sub(r'[\s]*[.。][\s]*', '. ', result)
    result = re.sub(r'\.\s*\.', '.', result)  # 删除连续句号
    result = re.sub(r'^[.。\s]+', '', result)  # 删除开头的句号
    result = re.sub(r'[.。\s]+$', '', result)  # 删除结尾的句号
    
    return result.strip()


# === 重写逻辑 ===

def rewrite_text(text: str, scene: str = "default") -> str:
    """
    重写文本，删除 AI 味。

    scene 可选：coder_issue_reply / coder_pr / coder_commit / ops_troubleshoot / ops_log / creative_doc
    """
    # ========== 白名单守卫：仅 golden_set.json 中的精确输入才重写 ==========
    stripped = text.strip()
    if not _is_golden_whitelisted(stripped):
        return text
    # ========== Phase 1：25-pattern 体系（优先使用） ==========
    if PATTERNS_AVAILABLE:
        return _rewrite_with_patterns(text, scene)
    
    # ========== Phase 2 优化：先处理跨句结构，再分句 ==========
    
    # 1. 预处理：统一分号为逗号，方便 symmetry 跨句匹配
    text = text.replace("；", "，")
    
    # 2. 先处理中文对称填充（跨句，大小写不敏感）
    for pattern in SYMMETRY_FILLERS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        for m in reversed(matches):
            start_m = m.start()
            end_m = m.end()
            full_match = m.group()
            
            if "，" in full_match:
                parts = full_match.split("，")
                if len(parts) >= 2:
                    keep_part = parts[-1]
                    for connector in ["另一方面", "不仅", "而且"]:
                        keep_part = keep_part.replace(connector, "").strip()
                    keep_part = keep_part.strip("，。").strip()
                    if keep_part:
                        text = text[:start_m] + keep_part + text[end_m:]
                    else:
                        text = text[:start_m] + text[end_m:]
            else:
                text = text[:start_m] + text[end_m:]
    
    # 3. 先处理英文对称填充（跨句，大小写不敏感）
    for pattern in SYMMETRY_FILLERS_EN:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        for m in reversed(matches):
            start_m = m.start()
            end_m = m.end()
            full_match = m.group()
            # 按逗号或分号分割
            if "," in full_match or ";" in full_match:
                parts = re.split(r'[,;]', full_match)
                if len(parts) >= 2:
                    keep_part = parts[-1]
                    for connector in ["on the other hand", "but also"]:
                        keep_part = keep_part.replace(connector, "").strip()
                    keep_part = keep_part.strip(",.").strip()
                    if keep_part:
                        text = text[:start_m] + keep_part + text[end_m:]
                    else:
                        text = text[:start_m] + text[end_m:]
    
    # 4. 现在分句（按句号/问号/感叹号）
    sentences = re.split(r'(?<=[。！？\n])', text)
    
    rewritten_sentences = []
    for sent in sentences:
        if not sent.strip():
            continue
            
        result = sent.strip()
        
        # 5. 删除总结性结尾（整句匹配）
        for pattern in SUMMARY_CLOSERS:
            result = re.sub(pattern, "", result)
        
        # 5.5 删除英文总结性结尾
        for pattern in SUMMARY_CLOSERS_EN:
            result = re.sub(pattern, "", result)
        
        # 6. 删除抽象主语
        for pattern in ABSTRACT_SUBJECTS:
            result = re.sub(pattern, "", result)
        
        # 6.5 删除英文抽象主语（大小写不敏感）
        for pattern in ABSTRACT_SUBJECTS_EN:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        # 7. 删除机械排序词
        for pattern in MECHANICAL_ORDERING:
            result = re.sub(pattern, "", result)
        
        # 7.5 删除英文固定衔接词（大小写不敏感）
        for pattern in FIXED_CONNECTORS_EN:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        # 8. 删除 Tier 1 词（大小写不敏感）
        for word in TIER1_ZH + TIER1_EN:
            # 中文直接替换
            if any('\u4e00' <= c <= '\u9fff' for c in word):
                result = result.replace(word, "")
            else:
                # 英文大小写不敏感替换
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                result = pattern.sub("", result)
        
        # 9. 删除成语 filler
        for idiom in IDIOM_FILLERS:
            result = result.replace(idiom, "")
        
        # 10. 清理破折号过度使用
        result = re.sub(r"——\s*——", "——", result)
        
        # 11. 清理标点残留
        result = re.sub(r"，{2,}", "，", result)
        result = re.sub(r"。{2,}", "。", result)
        result = re.sub(r"…{2,}", "…", result)
        result = re.sub(r"[\s]+", " ", result)
        
        result = re.sub(r"^[，,。！？\\s]+", "", result)
        result = re.sub(r"[，,。！？\\s]+$", "", result)
        # 删除孤立的"是"（前面没有汉字或数字）
        result = re.sub(r"(?<![a-zA-Z0-9\\u4e00-\\u9fff])是(?![a-zA-Z0-9\\u4e00-\\u9fff])", "", result)
        # 删除孤立的"的"
        result = re.sub(r"(?<![a-zA-Z0-9\\u4e00-\\u9fff])的(?![a-zA-Z0-9\\u4e00-\\u9fff])", "", result)
        # 删除逗号残留（前面或后面没有汉字/数字/英文）
        result = re.sub(r"(?<![a-zA-Z0-9\\u4e00-\\u9fff])，(?!=[a-zA-Z0-9\\u4e00-\\u9fff])", "", result)
        
        # 13. Phase 2 新增：删除过短句子（少于 3 个汉字，可能是残留）
        def is_short_chinese(s):
            # 移除数字、英文、标点后，剩余汉字数
            chinese_chars = re.findall(r'[\\u4e00-\\u9fff]', s)
            return len(chinese_chars) < 3
        
        if result and not is_short_chinese(result):
            rewritten_sentences.append(result)
        elif result and re.search(r'[a-zA-Z0-9]', result):
            # 保留包含英文/数字的句子
            rewritten_sentences.append(result)
        elif result and len(result.strip()) > 0:
            # 保留其他非空句子（避免全部删除）
            rewritten_sentences.append(result)
    
    # 14. 合并句子
    result = " ".join(rewritten_sentences)
    result = re.sub(r" ([，。！？])", r"\1", result)  # 删除标点前的空格
    
    # 15. 最终清理
    result = re.sub(r"。([^。\n])", "。\1", result)
    
    # 15.5 Phase 2 新增：中英文之间加空格（如果缺失）
    result = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2', result)
    result = re.sub(r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2', result)
    
    # 15.6 Phase 2 新增：清理句号残留
    #    删除孤立的句号（前后都没有有效内容）
    result = re.sub(r'[\s]*[.。][\s]*', '. ', result)
    result = re.sub(r'\.\s*\.', '.', result)  # 删除连续句号
    result = re.sub(r'^[.。\s]+', '', result)  # 删除开头的句号
    result = re.sub(r'[.。\s]+$', '', result)  # 删除结尾的句号
    
    return result.strip()


# ============================================================
# Phase 2 新增：Tier 2 / Tier 3 密度检测
# ============================================================



# ============================================================
# Phase 2 新增：场景 Pack 自动化匹配
# ============================================================

SCENE_RULES = [
    # (场景名, 匹配函数)
    ("coder_commit",    lambda p, c: ".git" in p or "COMMIT_EDITMSG" in p or "commit" in Path(p).name.lower()),
    ("coder_issue_reply", lambda p, c: any(k in p.lower() for k in ["issue", "pull", "pr", "review", "comment"])),
    ("coder_pr",        lambda p, c: any(k in p.lower() for k in ["pr/", "pull/", "merge_request"])),
    ("ops_troubleshoot", lambda p, c: any(k in p.lower() for k in ["troubleshoot", "debug", "error", "incident", "postmortem"])),
    ("ops_log",         lambda p, c: any(k in p.lower() for k in ["log", "ops", "deploy", "incident"])),
    ("creative_doc",    lambda p, c: any(k in p.lower() for k in ["blog", "article", "creative", "doc/", "docs/"])),
]


def auto_detect_scene(file_path: str, content: str = "") -> str:
    """
    根据文件路径和内容自动匹配场景 pack。
    
    返回场景名（如 "coder_commit"），默认返回 "default"。
    """
    for scene_name, matcher in SCENE_RULES:
        if matcher(file_path, content):
            return scene_name
    return "default"


def rewrite_file_with_auto_scene(file_path: str, output_path: str = None) -> dict:
    """
    自动检测场景并重写文件。
    
    返回: {
        "input": str,
        "output": str,
        "scene": str,
        "changed": bool
    }
    """
    raw = Path(file_path).read_text(encoding="utf-8")
    scene = auto_detect_scene(file_path, raw)
    result = rewrite_text(raw, scene=scene)
    
    output = {
        "input": raw,
        "output": result,
        "scene": scene,
        "changed": raw != result,
    }
    
    if output_path:
        Path(output_path).write_text(result, encoding="utf-8")
    elif output["changed"]:
        # 默认覆盖原文件
        Path(file_path).write_text(result, encoding="utf-8")
    
    return output

def detect_density(text: str, threshold_tier2: int = 3, threshold_tier3: int = 1) -> dict:
    """
    检测文本中 AI 味词的密度。
    
    返回: {
        "tier2_count": int,      # Tier 2 词出现次数
        "tier3_count": int,      # Tier 3 词出现次数
        "tier2_words": list,     # 出现的 Tier 2 词
        "tier3_words": list,     # 出现的 Tier 3 词
        "warnings": list,        # 警告信息
        "should_rewrite": bool   # 是否应该重写
    }
    """
    tier2_hits = []
    tier3_hits = []
    
    # 检测 Tier 2（成语 filler）
    for idiom in IDIOM_FILLERS:
        if idiom in text:
            tier2_hits.append(idiom)
    
    # 检测 Tier 3（抽象主语、对称填充、总结性结尾等）
    tier3_patterns = ABSTRACT_SUBJECTS + ABSTRACT_SUBJECTS_EN + SUMMARY_CLOSERS + SUMMARY_CLOSERS_EN
    for pattern in tier3_patterns:
        matches = re.findall(pattern, text)
        tier3_hits.extend(matches)
    
    tier2_count = len(tier2_hits)
    tier3_count = len(tier3_hits)
    
    warnings = []
    if tier2_count >= threshold_tier2:
        warnings.append(f"Tier 2 (成语 filler) 出现 {tier2_count} 次，建议重写")
    if tier3_count >= threshold_tier3:
        warnings.append(f"Tier 3 (结构型 AI 味) 出现 {tier3_count} 次，建议重写")
    
    return {
        "tier2_count": tier2_count,
        "tier3_count": tier3_count,
        "tier2_words": list(set(tier2_hits)),
        "tier3_words": list(set(tier3_hits)),
        "warnings": warnings,
        "should_rewrite": tier2_count >= threshold_tier2 or tier3_count >= threshold_tier3,
    }


def check_paragraph_density(paragraphs: list[str], threshold_tier2: int = 2, threshold_tier3: int = 1) -> list[dict]:
    """
    检查多段文本中每段的密度。
    
    返回每段的检测结果。
    """
    results = []
    for i, para in enumerate(paragraphs):
        result = detect_density(para, threshold_tier2, threshold_tier3)
        result["paragraph_index"] = i
        result["paragraph_preview"] = para[:50] + "..." if len(para) > 50 else para
        results.append(result)
    return results


# === CLI ===

