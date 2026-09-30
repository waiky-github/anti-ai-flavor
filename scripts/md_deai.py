#!/usr/bin/env python3
"""Markdown 感知的去 AI 味包装（2026-09-30）。

flavor core.rewrite_text 是纯文本设计：会把所有空白压成空格、句点后加空格，
直接喂整篇 markdown 会吞掉换行、毁掉结构、把 URL 里的点插空格。

本脚本：
  1) 整块保护：围栏代码块 / 标题行 / 独立图片行 / 表格 / HR / 引用块 → 原样保留
  2) 行内保护：行内代码 / URL / 自动链接 → 占位符，重写后还原
  3) 只对普通段落、列表行、引用行的文本部分逐块调用 rewrite_text
  4) 保留原始空行和块边界

用法:
  python3 md_deai.py 输入.md -o 输出.md [--diff] [--json 报告]
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "src")
)

from anti_ai_flavor.core import rewrite_text  # noqa: E402
from anti_ai_flavor.scoring import score_text  # noqa: E402

# 整块判定
_RE_FENCE = re.compile(r"^(\s{0,3})(`{3,}|~{3,})")
_RE_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
_RE_HR = re.compile(r"^\s{0,3}([-*_])\s*(\1\s*){2,}$")
_RE_TABLE = re.compile(r"^\s{0,3}\|.*\|\s*$")
_RE_IMAGE_ONLY = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")

# 行内保护
_RE_INLINE_CODE = re.compile(r"`[^`\n]+`")
_RE_AUTOLINK = re.compile(r"<https?://[^>\s]+>")
# markdown 链接 URL 部分 [txt](url)
_RE_MD_LINK = re.compile(r"(\]\()([^)\s]+)(\))")
# 裸 URL
_RE_BARE_URL = re.compile(r"https?://[^\s)）\]】>，。！？、]+")

# 占位符：含 CJK 字符，降低被规则当残留删掉的概率；用不常见组合
_PH_CODE = "\u200b内码\u200b{}\u200b"
_PH_URL = "\u200b网链\u200b{}\u200b"


def _protect_inline(text):
    """把行内代码/URL 换成占位符。返回 (文本, 还原表)。"""
    store = []

    def take(prefix, m):
        idx = len(store)
        store.append((prefix, m.group(0)))
        return _PH_CODE.format(idx) if prefix == "c" else _PH_URL.format(idx)

    # 顺序：先自动链接/行内代码，再 md 链接 URL，最后裸 URL
    text = _RE_INLINE_CODE.sub(lambda m: take("c", m), text)
    text = _RE_AUTOLINK.sub(lambda m: take("u", m), text)

    def _md(m):
        idx = len(store)
        store.append(("u", m.group(2)))
        return m.group(1) + _PH_URL.format(idx) + m.group(3)

    text = _RE_MD_LINK.sub(_md, text)
    text = _RE_BARE_URL.sub(lambda m: take("u", m), text)
    return text, store


def _restore_inline(text, store):
    # 多轮还原，防止占位符被规则拆碎
    for _ in range(3):
        for idx, (kind, val) in enumerate(store):
            ph = (_PH_CODE if kind == "c" else _PH_URL).format(idx)
            if ph in text:
                text = text.replace(ph, val)
    # 清掉残留零宽字符
    text = text.replace("\u200b", "")
    return text


def _clean_rewrite_noise(text):
    """修掉规则对占位符周边产生的小毛病。"""
    # 句点插空格可能波及占位符还原后的边界：restore 后 URL 完整，无需处理
    return text


def _rewrite_prose(text):
    """对一段纯文本（无换行）跑去味。"""
    if not text.strip():
        return text
    protected, store = _protect_inline(text)
    out = rewrite_text(protected)
    out = _restore_inline(out, store)
    out = _clean_rewrite_noise(out)
    return out.strip() if text.strip() else text


def deai(md: str) -> str:
    lines = md.split("\n")
    result = []
    i = 0
    n = len(lines)
    in_fence = False
    fence_marker = None

    while i < n:
        line = lines[i]

        # 围栏代码块：整块原样
        m = _RE_FENCE.match(line)
        if m:
            marker = m.group(2)[0]
            if not in_fence:
                in_fence = True
                fence_marker = marker
                result.append(line)
                i += 1
                continue
            if marker == fence_marker:
                in_fence = False
                fence_marker = None
                result.append(line)
                i += 1
                continue
        if in_fence:
            result.append(line)
            i += 1
            continue

        # 整块保护的行
        if (
            _RE_HEADING.match(line)
            or _RE_HR.match(line)
            or _RE_TABLE.match(line)
            or _RE_IMAGE_ONLY.match(line)
        ):
            result.append(line)
            i += 1
            continue

        # 空行保留
        if not line.strip():
            result.append(line)
            i += 1
            continue

        result.append(_rewrite_prose(line))
        i += 1

    return "\n".join(result)


def main():
    ap = argparse.ArgumentParser(description="Markdown 去 AI 味包装")
    ap.add_argument("file", help="输入 markdown")
    ap.add_argument("-o", "--output", help="输出文件（默认 stdout）")
    ap.add_argument("--diff", action="store_true", help="打印 diff")
    ap.add_argument("--json", help="把前后评分写入 JSON 文件")
    args = ap.parse_args()

    src = Path(args.file).read_text(encoding="utf-8")
    out = deai(src)

    before = score_text(src)
    after = score_text(out)
    report = {
        "file": args.file,
        "score_before": before.score,
        "score_after": after.score,
        "changed": src != out,
    }

    if args.diff and src != out:
        diff = difflib.unified_diff(
            src.splitlines(), out.splitlines(),
            fromfile=args.file, tofile=(args.output or "stdout"),
            lineterm="",
        )
        sys.stderr.write("\n".join(diff) + "\n")

    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(
            f"已写入: {args.output} | score {before.score} → {after.score}"
        )
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()
