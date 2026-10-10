"""元语言引用保护回归：代码标记 / 斜杠词条 / 表格 / 引号内的黑话不得被改写。

真实语料（researcher SessionDB 182 条长回复）验证发现：当 agent 讨论 flavor
项目本身、引用黑话词条时，短语引擎把这些「提及」当成正文「使用」来替换，
还跨斜杠/单元格拼出乱句。本测试锁定四类引用必须原样保留。
"""

import sys
sys.path.insert(0, "/home/agentuser/Projects/anti-ai-flavor/src")

from anti_ai_flavor.phrase_rewrite import phrase_rewrite

REFERENCE_CASES = [
    # 斜杠词条列举
    "gating 评分器和短语表是两套不相交词表：拉齐颗粒度/组合拳/品效合一都不扣分。",
    # Markdown 表格行（对照表）
    "| 拉齐颗粒度，组合拳打法形成合力，品效合一 | 统一下工作粒度 |",
    # 引号内引用
    'LLM 把“降本增效”换成了具体业务描述。',
    "LLM 把「降本增效」换成了具体业务描述。",
    'LLM 把 "降本增效" 换成了具体业务描述。',
    # 反引号代码标记（黑话词在标记内）
    "短语表 `PHRASE_RULES` 里收了 `组合拳` 等词。",
]


def test_references_preserved():
    for text in REFERENCE_CASES:
        out = phrase_rewrite(text)
        assert out == text, f"元语言引用被误改:\n  {text}\n  {out}"


def test_real_buzzword_body_still_cleaned():
    """对照：正文（非引用）里的黑话仍应被清洗。"""
    t = "产品能帮助客户实现降本增效的核心目标，为业务增长提供强有力的支撑。"
    out = phrase_rewrite(t)
    assert out != t
    assert "降低成本" in out
    assert "可靠保障" in out
