"""
patterns/p27_over_colloquial.py — Pattern 27: 过度口语化 / 网络烂梗

背景（2026-10-09 实证）：
    ai-eyes 公众号稿为了"说人话"，把「这玩意儿/智商税/傻傻/不香吗/社恐/抄作业/
    瞎扯淡/手忙脚乱」等网络热梗堆砌成篇，被用户判定轻佻、不专业。
    去 AI 味 ≠ 满口网络烂梗——目标是「专业但说人话」，不是从一个极端跳到另一个极端。

检测策略（只检测、不自动改写）：
    - 口语词自动替换极易毁语义（"这玩意儿"指什么取决于上下文），
      因此 fix 为空操作，命中只作为"重写信号"交给 LLM/人工。
    - 三档边界按「每百字硬/轻信号密度」划分：
        pass    硬信号 0 且 轻信号密度 < 阈值
        warn    少量轻信号（真人博主的正常口语）
        rewrite 出现硬信号，或轻信号过密
    - 误伤豁免：引述/代码/行内代码块内的命中不计。

调用：
    from .p27_over_colloquial import match, assess, fix
    hits = match(text)
    verdict = assess(text)   # {"severity": "pass/warn/rewrite", ...}
"""

from . import Match
import re
from typing import Any, Dict, List

# ============================================================
# 词表
# ============================================================

# 硬信号：网络烂梗 / 轻佻指代，科普正文中出现即应重写
HARD_SLANG = [
    "智商税", "傻傻", "不香吗", "抄作业", "社恐", "瞎扯淡", "活久见",
    "绝绝子", "yyds", "栓Q", "emo", "芭比Q", "躺平", "卷王", "打工人",
    "吃瓜", "炸裂", "逆天", "魔性", "上头", "下头", "破防", "拿捏",
    "笑死", "咱就说", "家人们", "宝子们", "铁子", "老铁",
    # 轻佻指代（对正经项目/技术的戏谑称呼）
    "这玩意儿", "那玩意儿", "玩意儿",
]

# 轻信号：口语化短语，单独出现正常，密集出现才扣分
LIGHT_COLLOQUIAL = [
    "说白了", "说实话", "说真的", "讲真", "怎么说呢", "你懂的",
    "手忙脚乱", "想破脑袋", "动嘴", "动动嘴", "冷冰冰", "活生生",
    "带点幽默感", "夹生", "火候", "菜谱", "买菜", "端到你面前",
    "万能钥匙", "万能金句", "百度百科", "八股文",
]

# 密度阈值（每 100 个非空白字符的命中数）
# 注意：短文本（<100 字）绝对数优先，否则 1 个轻信号也会被分母放大成高密。
# 最终判定 = 绝对数达标 且 密度达标。
LIGHT_DENSITY_WARN = 0.25      # 且 轻信号 ≥3 个 → warn
LIGHT_DENSITY_REWRITE = 0.55   # 且 轻信号 ≥6 个 → rewrite
LIGHT_COUNT_WARN = 3
LIGHT_COUNT_REWRITE = 6
# 硬信号绝对数阈值：出现即 rewrite（硬信号 0 个才可能 pass/warn）

# 代码/行内代码/引述保护：这些区域内的命中豁免
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_QUOTE_LINE_RE = re.compile(r"^\s*>.*$", re.MULTILINE)


def _masked_text(text: str) -> str:
    """把代码块/行内代码/引述行替换成等长空白，避免其中的口语词被计入。"""
    def _blank(m: re.Match) -> str:
        # 保留换行，避免影响"行数"语义；其余字符替换为空格
        return re.sub(r"[^\n]", " ", m.group(0))

    masked = _CODE_FENCE_RE.sub(_blank, text)
    masked = _INLINE_CODE_RE.sub(_blank, masked)
    masked = _QUOTE_LINE_RE.sub(_blank, masked)
    return masked


def _find_word(text: str, word: str) -> List[re.Match]:
    """找词；ASCII 词（如 yyds/emo）用词边界，CJK 词直接子串匹配。"""
    if re.fullmatch(r"[A-Za-z]+", word):
        return list(re.finditer(r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])",
                                text, re.IGNORECASE))
    return list(re.finditer(re.escape(word), text))


def match(text: str) -> List[Match]:
    """返回全部命中（硬信号 + 轻信号），suggested_fix 留空（不自动改写）。

    含跨词去重：被更长命中覆盖的短词不报（如「玩意儿」已被「这玩意儿」覆盖）。
    """
    masked = _masked_text(text)

    # 收集 (start, end)，硬信号在前，保留全部区间（硬/轻各自不覆盖）
    wanted: List[tuple] = []
    for word in HARD_SLANG:
        for m in _find_word(masked, word):
            wanted.append((m.start(), m.end()))
    for word in LIGHT_COLLOQUIAL:
        for m in _find_word(masked, word):
            wanted.append((m.start(), m.end()))

    # 同区间只留最长
    wanted.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept: List[tuple] = []
    for s, e in wanted:
        if any(s >= ks and e <= ke for ks, ke in kept):
            continue
        kept.append((s, e))
    kept.sort(key=lambda s: s[0])
    return [Match(s, e, masked[s:e], "") for s, e in kept]


def assess(text: str) -> Dict[str, Any]:
    """三档判定。

    返回：
        {
          "severity": "pass" | "warn" | "rewrite",
          "hard_hits": [str, ...],
          "light_hits": [str, ...],
          "light_density": float,   # 每百字轻信号数
          "n_chars": int,
        }
    """
    masked = _masked_text(text)
    n_chars = max(len(re.sub(r"\s", "", text)), 1)

    def _collect(words: List[str]) -> List[str]:
        """收集命中，自动跳过被更长词覆盖的短词（如 玩意儿 已被 这玩意儿 覆盖）。"""
        spans: List[tuple] = []  # (start, end, text)
        for word in words:
            for m in _find_word(masked, word):
                spans.append((m.start(), m.end(), m.group(0)))
        # 按起点升序、长度降序；同一区间只保留最长命中
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        kept: List[tuple] = []
        for s, e, t in spans:
            if any(s >= ks and e <= ke for ks, ke, _ in kept):
                continue  # 被已保留的更长命中覆盖
            kept.append((s, e, t))
        kept.sort(key=lambda s: s[0])
        return [t for _, _, t in kept]

    hard_hits = _collect(HARD_SLANG)
    light_hits = _collect(LIGHT_COLLOQUIAL)

    light_density = len(light_hits) / (n_chars / 100.0)

    if hard_hits or (
        len(light_hits) >= LIGHT_COUNT_REWRITE
        and light_density > LIGHT_DENSITY_REWRITE
    ):
        severity = "rewrite"
    elif (
        len(light_hits) >= LIGHT_COUNT_WARN
        and light_density > LIGHT_DENSITY_WARN
    ):
        severity = "warn"
    else:
        severity = "pass"

    return {
        "severity": severity,
        "hard_hits": hard_hits,
        "light_hits": light_hits,
        "light_density": round(light_density, 3),
        "n_chars": n_chars,
    }


def fix(text: str, match_obj: Match) -> str:
    """空操作：口语词不做自动替换，命中仅作为重写信号。"""
    return text
