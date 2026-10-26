"""段落/换行保真回归（2026-10-26）。

背景：`_cleanup_residue` 里的 `re.sub(r"[\\s]+", " ", text)` 会把所有空白折叠成
单空格，连空行也吃掉。实测把 15 段的小红书定稿压成 1 段，用户拿改写结果直接
发布就会毁掉排版。修复方式是用私用区哨兵占位、出口还原。

本文件锁住三件事：
  1. 段数与行数与原文一致（空行、段内单换行都不许动）；
  2. 100 分文本跑 rewrite 必须完全幂等（发布前闸门语义：不该改的一个字都不改）；
  3. 真的命中可修复 pattern 时，仍然能改（别把「保真」做成「什么都不改」）。
"""

from __future__ import annotations

import pathlib

import pytest

from anti_ai_flavor.core import rewrite_text
from anti_ai_flavor.scoring import score_text

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "name",
    ["promo_07_v3.txt", "promo_07_v5.txt", "promo_07_v8.txt", "promo_07_v9.txt"],
)
def test_paragraph_and_line_structure_preserved(name):
    """段数、行数必须零变化——排版是作者的决定，不是可清理的残留。"""
    original = _load(name)
    out = rewrite_text(original, scene="social-note")
    assert out.count("\n\n") == original.count("\n\n"), (
        f"{name} 空行段落被改动：{original.count(chr(10) * 2)} → {out.count(chr(10) * 2)}"
    )
    assert out.count("\n") == original.count("\n"), (
        f"{name} 换行数被改动：{original.count(chr(10))} → {out.count(chr(10))}"
    )


@pytest.mark.parametrize("name", ["promo_07_v8.txt", "promo_07_v9.txt"])
def test_clean_text_is_idempotent(name):
    """100 分定稿跑改写必须原样返回。

    发布前闸门最怕「明明 100 分，工具还是动了两笔」。只要动了一个字符，
    用户就得重新核对全文，闸门就从省事变成添乱。
    """
    original = _load(name)
    assert score_text(original, scene="social-note").score >= 85, "前置条件：这是干净稿"
    assert rewrite_text(original, scene="social-note") == original


def test_chinese_punctuation_no_trailing_space():
    """句号/逗号后不许夹半角空格（纯中文排版不夹空格）。"""
    src = "第一句。第二句，第三句"
    out = rewrite_text(src, scene="social-note")
    assert "。 " not in out and "， " not in out
    assert "第一句。" in out and "第二句，" in out


def test_still_rewrites_real_pattern():
    """保真不能变成什么都不改：真有可修复 pattern 时必须动手。"""
    src = "这不是一次普通的升级，而是一次彻底的架构重构。\n\n我们做了改动。"
    out = rewrite_text(src, scene="tech-doc")
    assert "不是" not in out or "而是" not in out, f"Not X but Y 未被改写：{out!r}"
    assert out.count("\n\n") == 1, "改写后段落结构应保持"


def test_blank_line_runs_collapse_to_single_paragraph_break():
    """连续多个空行归一成一个段落分隔，而不是被完全吃掉。"""
    src = "第一段。\n\n\n\n第二段。"
    out = rewrite_text(src, scene="base")
    assert "\n\n" in out
    assert out.count("\n\n") == 1
