"""短语级 AI 黑话改写（纯规则、0 token）。

与旧 Tier1「逐词删除、只删不补」不同，这里的操作单位是**短语**：
左边匹配一整段黑话固定搭配（含修饰词+动作+宾语），右边给一个**语法完整、
有动词有宾语**的人话短语，替换后句子依然成立。

设计约束：
  1. 长短语优先于短词（一次性整体替换，避免被短词先拆散）；
  2. 只做「替换」，不做「删除」——每条规则右侧都必须是非空完整短语；
  3. 匹配不到安全替换规则的词一律保留原词，绝不裸删（宁缺毋滥）；
  4. 受保护内容（代码/URL/版本/小数）在此之前已掩码，这里不会碰到。

主入口：``phrase_rewrite(text)``。
"""

from __future__ import annotations

import re
from typing import List, Tuple

from .lexicon import replacement_rules


# ---------------------------------------------------------------------------
# 受保护内容掩码
# ---------------------------------------------------------------------------

_FENCED = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`\n]+`")
_URL = re.compile(
    r"(?:https?://|www\.)[^\s\u4e00-\u9fff\uff0c\u3002\uff01\uff1f\uff1b\uff1a"
    r"\u3001\uff08\uff09\u3010\u3011]+"
)
_EMAIL = re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")
_PROTECT = (_FENCED, _INLINE, _URL, _EMAIL)


def _mask(text: str):
    saved: List[str] = []

    def _save(m):
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"

    for rx in _PROTECT:
        text = rx.sub(_save, text)
    return text, saved


def _unmask(text: str, saved: List[str]) -> str:
    return re.sub(
        r"\x00(\d+)\x00",
        lambda m: saved[int(m.group(1))],
        text,
    )


# ---------------------------------------------------------------------------
# 安全清理（不破坏语法）
# ---------------------------------------------------------------------------

_DUP_COMMA = re.compile(r"[,，]{2,}")
_DUP_SPACE = re.compile(r"[ \t]{2,}")
_ORPHAN_DE = re.compile(r"(全方位|多维度|深度|全面)的")


def _safe_cleanup(text: str) -> str:
    text = _DUP_COMMA.sub("，", text)
    text = _DUP_SPACE.sub(" ", text)
    text = _ORPHAN_DE.sub(r"\1", text)
    text = re.sub(r"\s+([，。！？；：）】」])", r"\1", text)
    return text.strip()


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

_COMPILED = [(re.compile(pat), repl) for pat, repl in replacement_rules()]


def phrase_rewrite(text: str) -> str:
    """短语级改写。只替换、不裸删；无规则的词保留；保护代码/URL。

    没有任何规则命中时原样返回（调用方据此判断是否需要走 LLM）。
    """
    if not text:
        return text
    masked, saved = _mask(text)
    s = masked
    changed = False
    for rx, repl in _COMPILED:
        new = rx.sub(repl, s)
        if new != s:
            changed = True
            s = new
    s = _safe_cleanup(s)
    out = _unmask(s, saved)
    return out if changed else text
