#!/usr/bin/env python3
"""anti_ai_flavor.dedup — 改写前的结构层去重 / 多版合并。

解决问题：
    待改写文本经常是「同一份内容的多个版本拼接」——例如同一份简历
    复制 3-4 次、每版措辞略有差异。逐段独立改写会把重复板块全部保留，
    读起来信息冗余、假。本模块在改写前先把结构压成「一份」。

设计：
    - 纯 stdlib（difflib），确定性、不烧 token
    - 以「段落」（空行分隔，回退到行）为单位
    - 精确重复直接去掉
    - 近似重复（归一化后相似度 >= 阈值）保留首次出现
    - 短行只做精确去重（短串模糊匹配容易误删，如技术名词）
"""
from __future__ import annotations

import re
import difflib
from typing import List, Tuple


def _normalize_for_dedup(s: str) -> str:
    """归一化：去 markdown 符号 / 空白 / 标点差异，让「同义重复」可比。

    注意不去掉中文/字母本身——保留语义骨架，只抹掉排版噪声。
    """
    s = s.lower()
    # markdown 标记：#、*、`、-、> 列表/标题符号
    s = re.sub(r'[#*`>\-]', ' ', s)
    # 所有空白压成一个
    s = re.sub(r'\s+', '', s)
    # 常见同义标点差异（顿号/逗号/斜杠/竖线）统一
    s = re.sub(r'[、，,/|·:：;；()（）\[\]【】."""\']', '', s)
    return s.strip()


def _split_paragraphs(text: str) -> List[str]:
    """按空行切段；若几乎没有空行，则按行切。"""
    if '\n\n' in text:
        # 保留段内换行（如列表块整体作为一个 paragraph）
        paras = re.split(r'\n\s*\n', text)
        return [p for p in paras]
    return text.split('\n')


def _is_near_duplicate(a: str, b: str, threshold: float) -> bool:
    """判断两个已归一化段落是否近似重复。

    - 长度相差太大直接否（difflib 在长度悬殊时给虚高 ratio）
    - 用 SequenceMatcher.ratio
    """
    if not a or not b:
        return a == b
    longer, shorter = (a, b) if len(a) >= len(b) else (b, a)
    # 短段长度 < 12 的不走模糊（交精确去重处理）
    if len(shorter) < 12:
        return False
    # 长度比 < 0.6 直接否
    if len(shorter) / len(longer) < 0.6:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold


def _strip_workpaper(text: str) -> str:
    """剥离混入正文的 AI 工作底稿 / 思维链噪声。

    这类内容常见于「让 AI 处理过但把过程也存下来」的文件：
      - <think>...</think> 思维链块
      - 英文工作指令：Let me analyze / Key things to do / Strict rules /
        section by section / Forbidden ... ✓ (not used)
      - 规则核对清单行（含 ✓/✗ 勾选）
    保留正常中文正文与短英文技术名词行。
    """
    # 1) <think>...</think> 或孤立的 <think> 到下一个正文标题
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)

    kept_lines: List[str] = []
    for line in text.split('\n'):
        s = line.strip()
        if not s:
            kept_lines.append(line)
            continue

        # 勾选核对行：含 ✓/✗ 几乎必是底稿
        if '✓' in s or '✗' in s:
            continue

        zh = len(re.findall(r'[一-鿿]', s))
        letters = len(re.findall(r'[A-Za-z]', s))

        # 英文为主的行：进一步判断是否工作底稿
        if letters > zh:
            # 工作底稿典型句式
            if re.search(
                r"(?i)\b(let me|i'll|i should|key things|strict rules?|"
                r"section by section|go through|re-?check|forbidden|"
                r"checklist|draft|analyze this|keep .* as-?is|mostly|"
                r"wait\b|note that|original:|rewrite|buzzword)",
                s,
            ):
                continue
            # 纯英文长句（>=5 个英文单词）且无中文 → 多半是底稿
            words = re.findall(r'[A-Za-z]+', s)
            if zh == 0 and len(words) >= 6:
                continue
            # 短英文行（如技术名词、分隔符）保留
        kept_lines.append(line)

    return '\n'.join(kept_lines)


def deduplicate_text(
    text: str,
    *,
    similarity_threshold: float = 0.90,
    strip_workpaper: bool = True,
) -> Tuple[str, dict]:
    """段落级去重，返回 (去重后文本, 统计信息)。

    参数：
      similarity_threshold：近似判定阈值（0-1），默认 0.90。
          越高越保守（只删几乎一样的），越低越激进。
      strip_workpaper：是否先剥离 AI 工作底稿/思维链噪声，默认 True。

    返回：
      (deduped_text, stats)，stats 含 removed_exact / removed_near /
      before_chars / after_chars。
    """
    original_len = len(text)
    if strip_workpaper:
        text = _strip_workpaper(text)
    paragraphs = _split_paragraphs(text)

    kept: List[str] = []
    kept_norm: List[str] = []
    seen_exact: set = set()
    removed_exact = 0
    removed_near = 0

    for para in paragraphs:
        if not para.strip():
            # 保留空行分隔（去重后仍需排版），但不连续堆积
            if kept and kept[-1].strip():
                kept.append(para)
            continue

        norm = _normalize_for_dedup(para)

        # 1) 精确重复
        if norm in seen_exact:
            removed_exact += 1
            continue

        # 2) 近似重复（短段只做精确，不做模糊）
        is_dup = False
        if len(norm) >= 12:
            for existing in kept_norm:
                if _is_near_duplicate(norm, existing, similarity_threshold):
                    is_dup = True
                    break
        if is_dup:
            removed_near += 1
            continue

        seen_exact.add(norm)
        kept_norm.append(norm)
        kept.append(para)

    deduped = '\n\n'.join(p.strip('\n') for p in kept if p is not None)
    # 清理 3+ 连续换行
    deduped = re.sub(r'\n{3,}', '\n\n', deduped).strip()

    stats = {
        'workpaper_chars_removed': original_len - len(text) if strip_workpaper else 0,
        'removed_exact': removed_exact,
        'removed_near': removed_near,
        'paragraphs_before': len([p for p in paragraphs if p.strip()]),
        'paragraphs_after': len([p for p in kept if p.strip()]),
        'before_chars': original_len,
        'after_chars': len(deduped),
    }
    return deduped, stats
