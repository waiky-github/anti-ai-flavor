"""phrase_rewrite.phrase_rewrite 单测。

核心契约：
  - 黑话短语被替换成语法完整的人话（不是删空）；
  - 无规则命中的词保留原词；
  - 版本/小数/URL/代码/邮箱不受影响；
  - 结果里不残留「赋能/闭环/生态」等被部分处理的坏搭配。
"""

from anti_ai_flavor.phrase_rewrite import phrase_rewrite as pr


def test_funeng_yehu_replaced_whole():
    s = "我们将全方位深度赋能核心业务闭环。"
    out = pr(s)
    assert "赋能" not in out
    assert "闭环" not in out
    assert "支撑核心业务" in out
    # 句子主干完整
    assert out.startswith("我们将") and out.endswith("。")


def test_shengtai_replaced():
    s = "聚力深度打造数智化新生态，持续投入。"
    out = pr(s)
    assert "生态" not in out
    assert "建设数智化平台" in out


def test_tigong_zhicheng():
    s = "为核心链路提供强有力的战略支撑。"
    out = pr(s)
    assert "战略支撑" not in out
    assert "可靠保障" in out or "稳定" in out


def test_jiali_zuzhi_luodi():
    s = "助力业务价值最大化落地。"
    out = pr(s)
    assert "价值最大化" not in out
    assert "实际收益" in out


def test_huiyi_heihua():
    s = "先拉通对齐，把这件事形成闭环，形成可复用的方法论。"
    out = pr(s)
    assert "拉通对齐" not in out
    assert "闭环" not in out
    assert "方法论" not in out
    assert "对齐目标" in out
    assert "落实到位" in out
    assert "可复用的做法" in out


def test_no_rule_word_preserved():
    # 没有对应改写规则的正常句子应原样保留
    s = "我们明天上午开会讨论接口设计和数据库索引。"
    assert pr(s) == s


def test_version_number_untouched():
    s = "版本 v1.2.3 保持不变，阈值 3.14。"
    out = pr(s)
    assert "v1.2.3" in out
    assert "3.14" in out


def test_url_and_code_untouched():
    s = "见 https://a.com/x,y?q=1 ，调用 f(a, b) 即可。"
    out = pr(s)
    assert "https://a.com/x,y?q=1" in out
    assert "f(a, b)" in out


def test_email_untouched():
    s = "发到 a.b@mail.example.com 邮箱。"
    out = pr(s)
    assert "a.b@mail.example.com" in out


def test_idempotent():
    samples = [
        "全方位深度赋能核心业务闭环，打造数智化生态。",
        "拉通对齐，形成可复用的方法论，助力落地。",
    ]
    for s in samples:
        once = pr(s)
        assert pr(once) == once
