"""p05/p10 形态闸门 + p14 收窄 + 「展示了」豁免的回归锁（2026-11-04）。

三个改动都是「收窄误报」，收窄最容易的退化方式是下一次有人把正则改宽回来，
而且不会红任何测试。本文件把三处的正反两面都钉住：

  - 反例（真人技术文片段）不许命中
  - 正例（真 AI 腔）必须命中

数据来源：74 对真人/AI 对照集 + 78 篇真人长文（corpus/human_aliyun）。
"""

import pytest

from anti_ai_flavor.scoring import score_text, _parallel_item_len

TECH = "tech-doc"

# 841692（阿里云 iptables 文章）里被误判成三项式的原句，实测切出的三个「并列项」
# 裸长度分别是 20/27/19 字——是同一句话的分句，不是排比。
HUMAN_CLAUSE_SPLIT = (
    "其中表是按照对数据包的操作区分（过滤， NAT等）的，"
    "链是按照不同的 Hook 点来区分的，表和链实际上是netfilter的两个维度。"
)

# 同一篇文章的上下文，用于整篇级回归：真人技术文必须 pass。
HUMAN_TECH_DOC = (
    "iptables 的规则组织方式常被误解。实际上它分成表和链两层："
    + HUMAN_CLAUSE_SPLIT
    + " 数据包进入内核后，会依次经过 PREROUTING、INPUT、FORWARD、OUTPUT、"
    "POSTROUTING 这几个挂载点，每个挂载点上可以挂多个链。规则的匹配是线性遍历，"
    "命中第一条就执行对应动作，因此规则顺序会直接影响行为。"
)

# 真 AI 腔的三项式：每项都是短短语，闸门不该把它拦掉。
AI_TRIAD = "它不仅显著提升了性能，还有效降低了成本，同时全面优化了体验。"

# 真 AI 腔的四项罗列（四项都是抽象词，四项式该由 p10 命中）。
AI_FOUR_ITEMS = "方案强调全面、深度、维度、层面。"


def _hits(text, scene=TECH):
    return score_text(text, scene=scene).hits


def _cats(text, scene=TECH):
    return [h.pattern_id or h.category for h in _hits(text, scene)]


# ---------------- p05 / p10 形态闸门 ----------------


def test_parallel_items_split_by_clause_not_flagged():
    """跨逗号切出来的长「并列项」不是排比，不应命中 p05/p10。"""
    cats = _cats(HUMAN_CLAUSE_SPLIT)
    assert "p05_forced_triads" not in cats
    assert "p10_list_fatigue" not in cats


def test_short_phrase_triad_still_flagged():
    """闸门不能把真正的短短语三项式一起放过。"""
    assert "p05_forced_triads" in _cats(AI_TRIAD)


def test_short_phrase_four_item_list_still_flagged():
    assert "p10_list_fatigue" in _cats(AI_FOUR_ITEMS)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("、它不仅显著提升了性能，", 10),   # 首尾标点剥掉
        ("（过滤， NAT等）的，", 10),         # 全角括号 + 空格剥掉
        ("", 0),
    ],
)
def test_parallel_item_len_strips_wrappers(raw, expected):
    assert _parallel_item_len(raw) == expected


def test_parallel_item_len_tolerates_none():
    """groups() 理论上可能给出 None，辅助函数不能因此炸。"""
    assert _parallel_item_len(None) == 0


# ---------------- p14 名词化不许跨分句 ----------------


def test_p14_does_not_cross_clause():
    """命中原句的其实是后半句的「决定」，与「进行」隔着逗号，不算名词化。"""
    assert "p14_nominalization" not in _cats(HUMAN_CLAUSE_SPLIT)
    assert "p14_nominalization" not in _cats(
        "对数据包进行过滤，具体的规则要求决定如何处理一个数据包。"
    )


@pytest.mark.parametrize(
    "sentence",
    [
        "我们对查询逻辑进行了全面优化。",
        "项目组对部署流程做出了改进。",
        "团队进行了优化。",
    ],
)
def test_p14_still_flags_short_nominalization(sentence):
    assert "p14_nominalization" in _cats(sentence)


# ---------------- 「展示了」场景豁免 ----------------


@pytest.mark.parametrize("sentence", ["本文展示了 netfilter 的钩子机制。", "示例展示了规则匹配流程。"])
def test_zhanshile_exempt_in_tech_doc(sentence):
    hits = _hits(sentence, scene=TECH)
    assert not [h for h in hits if h.matched_text == "展示了"]


@pytest.mark.parametrize("sentence", ["本文展示了 netfilter 的钩子机制。", "示例展示了规则匹配流程。"])
def test_zhanshile_still_penalized_in_base_scene(sentence):
    """豁免只对 tech-doc 生效，别的场景「展示了」仍是套话。"""
    hits = _hits(sentence, scene="base")
    assert [h for h in hits if h.matched_text == "展示了"]


# ---------------- 端到端：真人 pass / AI 不 pass ----------------


def test_human_netfilter_article_passes():
    res = score_text(HUMAN_TECH_DOC, scene=TECH)
    assert res.action == "pass", f"真人技术文被误判：raw={res.raw} hits={[h.pattern_id or h.category for h in res.hits]}"
    assert res.score >= 85
    # 钉死 0 分扣：闸门没生效时这里会是 4 分（p05×2 + p10×2 的伪并列），
    # 单靠 action=pass 挡不住——旧版也能靠 raw<=5 的保底混过去。
    assert res.raw == 0, f"仍有伪并列扣分：{[ (h.pattern_id, h.matched_text) for h in res.hits ]}"


def test_ai_tech_article_still_not_pass():
    """假阴性守卫：放宽三处之后，典型 AI 技术文仍须被拦下。"""
    from test_tech_doc_false_positive import _AI_TECH_ARTICLE

    res = score_text(_AI_TECH_ARTICLE, scene=TECH)
    assert res.action != "pass", f"AI 技术文漏检：score={res.score} raw={res.raw}"
