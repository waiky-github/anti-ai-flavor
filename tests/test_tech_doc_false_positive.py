"""tech-doc 场景误报修正的回归测试（2026-11-03）。

背景：78 篇真人阿里云技术文 / 115 万字实测，原误判率 20.5%（16/78）。
根因四条：
  1. 代码块参与检测——p26/p23 的命中 93% 落在代码里；
  2. 代码占字符量 58% 却计入分母——「代码多、正文 AI 味重」假及格（漏检）；
  3. 技术术语被当 AI 味：唯一 ID / 引擎 / 利用率 / 首先 / 从而；
  4. p36 序数排除表不全——「第一个 token / 第一级目录」被判绝对化。

修正后 3.8%（3/78）。本文件锁住这些行为，防止回退。
"""
import pytest

from anti_ai_flavor.scoring import _strip_code_blocks, score_text


# ---------- 1. 代码块剥离 ----------

def test_strip_fenced_and_inline_code():
    text = "说明文字。\n```python\nprint('hello')\n```\n结尾。"
    body = _strip_code_blocks(text)
    assert "print" not in body
    assert "说明文字" in body
    assert "结尾" in body


def test_strip_inline_code_keeps_surrounding_prose():
    body = _strip_code_blocks("配置 `p05` 参数后重启。")
    assert "p05" not in body
    assert "配置" in body and "参数后重启" in body


def test_code_heavy_doc_falls_back_to_full_text():
    """正文不足 200 字而原文很长 → 视为几乎全是代码，退回全文，避免分母趋零。"""
    code = "```bash\n" + "echo hello\n" * 80 + "```"
    r = score_text("一行说明。" + code, scene="tech-doc")
    assert 0 <= r.score <= 100


# ---------- 2. tech-doc 词级豁免 ----------

@pytest.mark.parametrize("sentence", [
    "把 GPU 引擎升级到最新版本。",
    "Unity 引擎的资源加载机制。",
    "这样能有效降低延迟。",
    "从而减少重复请求。",
    "各类各种场景下都要验证。",
])
def test_tech_doc_terms_not_penalized(sentence):
    r = score_text(sentence, scene="tech-doc")
    assert r.raw == 0, f"技术术语被误判: {[h.matched_text for h in r.hits]}"


def test_same_terms_still_penalized_outside_tech_doc():
    """豁免只对 tech-doc 生效，其他场景不能跟着放宽。"""
    r = score_text("这样能有效降低延迟。", scene="social-note")
    assert r.raw > 0


# ---------- 3. p36 序数 vs 吹嘘 ----------

@pytest.mark.parametrize("sentence", [
    "第一个 token 的耗时最长。",
    "第一级目录用 1 位 16 进制命名。",
    "第一行是表头。",
    "第一步先建索引。",
    "PG 是唯一可行的模型并行方式。",
    "集群将生成唯一 ID。",
])
def test_p36_ordinal_and_data_terms_not_flagged(sentence):
    r = score_text(sentence, scene="tech-doc")
    assert r.raw == 0, f"序数/数据属性被误判: {[h.matched_text for h in r.hits]}"


@pytest.mark.parametrize("sentence", [
    "它是唯一能够满足所有场景的选择。",
    "这是唯一可以彻底解决问题的方案。",
])
def test_p36_hype_still_flagged(sentence):
    r = score_text(sentence, scene="tech-doc")
    assert r.raw > 0, "吹嘘语境仍须计分"


# ---------- 4. legacy 类目罚分可被 profile 覆盖 ----------

def test_legacy_category_penalty_override_applies():
    text = "首先，配置环境。最后，启动服务。"
    doc = score_text(text, scene="tech-doc")
    note = score_text(text, scene="social-note")
    doc_mech = [h.penalty for h in doc.hits if h.category == "mechanical_ordering"]
    note_mech = [h.penalty for h in note.hits if h.category == "mechanical_ordering"]
    assert doc_mech and note_mech
    assert doc_mech[0] == 1, "tech-doc 应降权到 1 分"
    assert note_mech[0] == 3, "其他场景应保持 3 分"


# ---------- 5. 假阴性守卫：AI 技术文不能被放宽放过 ----------

_AI_TECH_ARTICLE = """在当今云计算快速发展的时代，Kubernetes 已经成为容器编排领域的事实标准。本文将深入探讨性能优化的核心要点，旨在帮助读者全面掌握相关技术，为业务的稳定运行保驾护航。

值得注意的是，性能优化在整个系统架构中扮演着至关重要的角色。它不仅能够显著提升系统的响应速度，还能够有效降低资源消耗，为业务的持续增长奠定坚实的基础。

首先，我们需要深入理解资源调度的底层逻辑。其次，要充分利用其强大的自动扩缩容能力。最后，通过持续监控和调优实现系统的高效运转。这三个维度相辅相成，构成了完整的优化体系。

合理的资源配置是性能优化的基石。通过精准设置参数，我们可以有效避免资源争抢，从而确保关键业务的稳定运行。需要注意的是，资源配置需要在稳定性和成本之间找到平衡点。

综上所述，性能优化是一个持续演进的过程。通过深入理解机制、合理配置参数、优化策略与网络性能，我们能够全面提升集群的整体性能表现。展望未来，性能优化将迎来更多新的机遇与挑战。希望本文能够为读者提供有价值的参考，助力大家在云原生之路上行稳致远。"""


def test_ai_tech_article_still_blocked():
    r = score_text(_AI_TECH_ARTICLE, scene="tech-doc")
    assert r.score < 60, f"AI 技术文应被拦下，实际 {r.score}（raw={r.raw}）"
    assert r.action in ("rewrite", "block")
