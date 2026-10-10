"""中文标点符号规范化（纯规则、0 token、幂等）。

由 gateway hook 在回复发出前调用。设计原则：

1. 只在「中文相邻」时把半角标点转全角，纯英文句子不受影响；
2. 句号 / 逗号 / 冒号有数字守卫，不碰小数、版本号、千分位、时间；
3. 代码块 / 行内代码 / URL / email 整体掩码，内部标点一律不动；
4. 括号成对转换，避免中文语境里半角括号只转一半的错配；
5. 折叠重复标点，清理中文与标点间多余空格。

对外主入口：``normalize_punctuation(text)``。
"""

from __future__ import annotations

import re
from typing import List, Tuple

# ---------------------------------------------------------------------------
# 字符集
# ---------------------------------------------------------------------------

# 汉字（与 gateway_hook._CJK_RE 保持一致）
_CJK = r"\u4e00-\u9fff"
_CJK_RE = re.compile(f"[{_CJK}]")
# 中文标点也算「中文相邻」，处理 "你好，!" 这类连续场景
_CJK_PUNCT = r"\u3000-\u303f\uff00-\uffef\u2026"
_NEAR_RE = re.compile(f"[{_CJK}{_CJK_PUNCT}]")


def _is_cjk(ch: str) -> bool:
    return bool(ch) and _NEAR_RE.match(ch) is not None


def _is_alnum_ascii(ch: str) -> bool:
    return bool(ch) and ("a" <= ch <= "z" or "A" <= ch <= "Z" or "0" <= ch <= "9")


# ---------------------------------------------------------------------------
# 受保护区域（代码 / URL / email）整体掩码
# ---------------------------------------------------------------------------

_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s\u4e00-\u9fff\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u3001"
    r"\uff08\uff09\u3010\u3011\u300c\u300d\u300e\u300f]+"
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")

_PROTECT_RES = (_FENCED_CODE_RE, _INLINE_CODE_RE, _URL_RE, _EMAIL_RE)


def _mask_protected(text: str) -> Tuple[str, List[str]]:
    """把受保护区段替换成不含标点/汉字的占位符 \\x00<i>\\x00。"""
    saved: List[str] = []

    def _save(m: re.Match) -> str:
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"

    for rx in _PROTECT_RES:
        text = rx.sub(_save, text)
    return text, saved


def _unmask(text: str, saved: List[str]) -> str:
    def _restore(m: re.Match) -> str:
        idx = int(m.group(1))
        return saved[idx] if 0 <= idx < len(saved) else m.group(0)

    return re.sub(r"\x00(\d+)\x00", _restore, text)


# ---------------------------------------------------------------------------
# 省略号（先于句号处理）
# ---------------------------------------------------------------------------

# 3 个及以上半角句点
_DOTS_RE = re.compile(r"\.{3,}")
# 一个及以上中文省略号字符
_ELLIPSIS_RE = re.compile(r"\u2026{1,}")


def _adjacent_cjk(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return _is_cjk(before) or _is_cjk(after)


def _normalize_ellipsis(text: str) -> str:
    def _dots(m: re.Match) -> str:
        return "\u2026\u2026" if _adjacent_cjk(text, m.start(), m.end()) else m.group(0)

    text = _DOTS_RE.sub(_dots, text)

    def _ell(m: re.Match) -> str:
        return "\u2026\u2026" if _adjacent_cjk(text, m.start(), m.end()) else m.group(0)

    text = _ELLIPSIS_RE.sub(_ell, text)
    return text


# ---------------------------------------------------------------------------
# 半角括号成对转换
# ---------------------------------------------------------------------------

_PAREN_RE = re.compile(r"\(([^()\n]*)\)")


def _normalize_parens(text: str) -> str:
    """括号内含中文、或括号紧贴中文时，两侧括号一起转全角。跑两轮覆盖浅嵌套。"""

    def _conv(m: re.Match) -> str:
        inner = m.group(1)
        before = text[m.start() - 1] if m.start() > 0 else ""
        after = text[m.end()] if m.end() < len(text) else ""
        if _CJK_RE.search(inner) or _is_cjk(before) or _is_cjk(after):
            return "\uff08" + inner + "\uff09"
        return m.group(0)

    for _ in range(2):
        new = _PAREN_RE.sub(_conv, text)
        if new == text:
            break
        text = new
    return text


# ---------------------------------------------------------------------------
# 半角 → 全角（逐字符，带上下文守卫）
# ---------------------------------------------------------------------------

# 逗号/分号/冒号/叹号/问号：中文相邻即转。句号单独加数字守卫。
_SIMPLE_MAP = {
    ",": "\uff0c",
    ";": "\uff1b",
    ":": "\uff1a",
    "!": "\uff01",
    "?": "\uff1f",
}


def _convert_halfwidth(text: str) -> str:
    out: List[str] = []
    for i, ch in enumerate(text):
        prev = text[i - 1] if i > 0 else ""
        nxt = text[i + 1] if i + 1 < len(text) else ""
        near_cjk = _is_cjk(prev) or _is_cjk(nxt)

        if ch in _SIMPLE_MAP and near_cjk:
            out.append(_SIMPLE_MAP[ch])
            continue
        if ch == "." and near_cjk:
            # 数字守卫：两侧只要有 ASCII 字母/数字就不动（小数/版本/缩写）
            if not _is_alnum_ascii(prev) and not _is_alnum_ascii(nxt):
                out.append("\u3002")
                continue
        out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# 重复标点折叠
#
# 分两步：转换前先把「半角/全角混合」的重复串折叠成单个半角（避免逐个转换时
# 只有紧邻中文的第一个被转、其余半角残留成 x！!!x 这种混合串），转换后再对
# 全角做一次兜底折叠。
# ---------------------------------------------------------------------------

# (混合宽度重复串, 折叠目标=单个半角)
_PRECOLLAPSE = [
    (re.compile(r"[!！]{2,}"), "!"),
    (re.compile(r"[?？]{2,}"), "?"),
    (re.compile(r"\.{2,}"), "."),
    (re.compile(r"[,，]{2,}"), ","),
    (re.compile(r"[;；]{2,}"), ";"),
    (re.compile(r"[:：]{2,}"), ":"),
]

_COLLAPSE_RES = [
    re.compile(p) for p in (
        r"\uff01{2,}",   # ！！
        r"\uff1f{2,}",   # ？？
        r"\u3002{2,}",   # 。。
        r"\uff0c{2,}",   # ，，
        r"\uff1b{2,}",   # ；；
        r"\uff1a{2,}",   # ：：
        r"\u2026\u2026+",  # 多组省略号 -> 一组
    )
]
_COLLAPSE_TO = ["\uff01", "\uff1f", "\u3002", "\uff0c", "\uff1b", "\uff1a", "\u2026\u2026"]


def _precollapse_runs(text: str) -> str:
    """半/全角重复串（贴近中文、且不贴数字）折叠成单个半角。"""
    def make_sub(rx: re.Pattern, repl: str):
        def _sub(m: re.Match) -> str:
            before = text[m.start() - 1] if m.start() > 0 else ""
            after = text[m.end()] if m.end() < len(text) else ""
            if not (_is_cjk(before) or _is_cjk(after)):
                return m.group(0)
            # 贴着 ASCII 字母/数字时保守不动（小数/版本/数字分隔等）
            if _is_alnum_ascii(before) or _is_alnum_ascii(after):
                return m.group(0)
            return repl
        return _sub

    for rx, repl in _PRECOLLAPSE:
        text = rx.sub(make_sub(rx, repl), text)
    return text


def _collapse_repeats(text: str) -> str:
    for rx, to in zip(_COLLAPSE_RES, _COLLAPSE_TO):
        text = rx.sub(to, text)
    return text


# ---------------------------------------------------------------------------
# 空格清理
# ---------------------------------------------------------------------------

# 两个汉字（或中文标点相邻）之间的空格
_CJK_SPACE_CJK = re.compile(f"([{_CJK}])[ \\t]+([{_CJK}])")
# 标点前 / 后的空格
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([，。！？；：、）】」』…])")
_SPACE_AFTER_PUNCT = re.compile(r"([（【「『])[ \t]+")


def _clean_spaces(text: str) -> str:
    # 循环以处理 "你 好 世 界" 链
    prev = None
    while prev != text:
        prev = text
        text = _CJK_SPACE_CJK.sub(r"\1\2", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _SPACE_AFTER_PUNCT.sub(r"\1", text)
    return text


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def normalize_punctuation(text: str) -> str:
    """规范化中文标点。不改动代码 / URL / 数字；幂等。"""
    if not text:
        return text
    masked, saved = _mask_protected(text)
    s = _normalize_ellipsis(masked)
    s = _precollapse_runs(s)
    s = _normalize_parens(s)
    s = _convert_halfwidth(s)
    s = _collapse_repeats(s)
    s = _clean_spaces(s)
    return _unmask(s, saved)


# ---------------------------------------------------------------------------
# 受保护 token 完整性校验（用于判断 LLM 改写是否破坏了 URL/版本/邮箱）
# ---------------------------------------------------------------------------

# 版本号 v1.2.3 / 1.2.3（至少含一个点，段为字母数字）
_VERSION_RE = re.compile(r"\bv?\d+(?:\.\d+){1,4}\b")
# 千分位数字 1,000,000
_THOUSANDS_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")
# 时间 12:30(:00)
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")


def extract_protected_tokens(text: str) -> List[str]:
    """提取不该被改写破坏的关键 token：URL/邮箱/版本号/千分位/时间。"""
    tokens: List[str] = []
    for rx in _PROTECT_RES:
        tokens.extend(m.group(0) for m in rx.finditer(text))
    for rx in (_VERSION_RE, _THOUSANDS_RE, _TIME_RE):
        tokens.extend(m.group(0) for m in rx.finditer(text))
    # 去重保序
    seen = set()
    out = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def protected_tokens_preserved(before: str, after: str) -> bool:
    """改写后原文中的关键 token 是否全部完整保留（逐字出现）。

    任一关键 token 在改写结果中找不到（被删/被改/被插空格）即判 False。
    """
    for tok in extract_protected_tokens(before):
        if tok not in after:
            return False
    return True
