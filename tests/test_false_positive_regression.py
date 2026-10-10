"""误伤回归：「形成合力」「反哺」在正常工程语境不得被改写/扣分。

背景：批量真实样本验证发现这两个词曾被当黑话单点替换（合力→一起发力、
反哺→带动），但它们在工程文本里是正常中文——只在整句黑话堆叠时才是信号。
本测试锁定：引擎必须原样保留这些正常用法。
"""

import sys
sys.path.insert(0, "/home/agentuser/Projects/anti-ai-flavor/src")

from anti_ai_flavor.phrase_rewrite import phrase_rewrite
from anti_ai_flavor.scoring import score_text
from anti_ai_flavor.lexicon import residual_keywords

# (原文, 必须原样保留的关键短语)
NORMAL_CASES = [
    ("前端和后端需要形成合力，才能在月底前完成联调。", "形成合力"),
    ("新增的缓存模块会反哺下游的报表服务，减少重复查询。", "反哺下游"),
]


def test_normal_phrases_not_rewritten():
    for text, keep in NORMAL_CASES:
        out = phrase_rewrite(text)
        assert out == text, f"正常文本被误伤:\n  {text}\n  {out}"
        assert keep in out


def test_normal_phrases_not_in_residual():
    """「合力」「反哺」不得作为残留检测关键词（避免正常用法被扣分）。"""
    kws = residual_keywords()
    assert "合力" not in kws
    assert "反哺" not in kws


def test_normal_phrases_score_not_penalized():
    for text, _ in NORMAL_CASES:
        s = score_text(text).score
        assert s >= 85, f"正常文本被低分 {s}: {text}"


def test_buzzword_sentence_still_cleaned():
    """对照：整句黑话堆叠时仍靠强信号改净（不因移除单词规则而漏网）。"""
    t = "团队通过组合拳打法形成合力，真正做到品效合一。"
    out = phrase_rewrite(t)
    assert "组合拳" not in out
    assert "品效合一" not in out
