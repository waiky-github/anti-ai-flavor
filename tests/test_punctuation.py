"""punctuation.normalize_punctuation 单测：转换正确性 + 误伤守卫 + 幂等。"""

from anti_ai_flavor.punctuation import normalize_punctuation as np_


# ---------------------------------------------------------------------------
# 正常转换
# ---------------------------------------------------------------------------

def test_basic_sentence():
    assert np_("你好,世界.") == "你好，世界。"


def test_full_punctuation_set():
    out = np_("他说:快走!走了吗;是的,对.")
    assert out == "他说：快走！走了吗；是的，对。"


def test_question_mark():
    assert np_("这是什么?") == "这是什么？"


def test_parens_pair_with_cjk_inside():
    assert np_("这是(注释)内容") == "这是（注释）内容"


def test_parens_pair_adjacent_to_cjk():
    assert np_("见(note)") == "见（note）"


def test_ellipsis_from_dots():
    assert np_("等等……") == "等等……"
    assert np_("等等......") == "等等……"


# ---------------------------------------------------------------------------
# 误伤守卫
# ---------------------------------------------------------------------------

def test_english_sentence_untouched():
    s = "Hello, world. This is a test!"
    assert np_(s) == s


def test_decimal_number_untouched():
    s = "结果是3.14和2.5。"
    assert np_(s) == "结果是3.14和2.5。"


def test_version_number_untouched():
    s = "版本 v1.2.3 已发布。"
    assert np_(s) == "版本 v1.2.3 已发布。"


def test_thousands_separator_untouched():
    s = "总量为1,000,000元。"
    assert np_(s) == "总量为1,000,000元。"


def test_time_colon_untouched():
    s = "会议在12:30开始。"
    assert np_(s) == "会议在12:30开始。"


def test_url_untouched():
    s = "详见 https://a.com/x,y?q=1:2 哦。"
    out = np_(s)
    assert "https://a.com/x,y?q=1:2" in out
    assert out.endswith("哦。")


def test_email_untouched():
    s = "发到 a.b+c@mail.example.com 邮箱。"
    out = np_(s)
    assert "a.b+c@mail.example.com" in out
    assert out.endswith("邮箱。")


def test_inline_code_untouched():
    s = "调用 f(a, b) 即可，试试。"
    out = np_(s)
    assert "f(a, b)" in out
    assert out.startswith("调用")


def test_fenced_code_untouched():
    s = "代码如下:\n```\nx = 1, 2, 3\nprint(x)\n```\n完成。"
    out = np_(s)
    assert "x = 1, 2, 3" in out
    assert "print(x)" in out
    assert out.endswith("完成。")
    assert "代码如下：" in out


def test_english_parens_untouched():
    s = "The function f(x) returns 1."
    assert np_(s) == s


# ---------------------------------------------------------------------------
# 重复标点折叠
# ---------------------------------------------------------------------------

def test_collapse_repeated_exclamation():
    assert np_("太好了!!!") == "太好了！"


def test_collapse_repeated_question():
    assert np_("真的吗???") == "真的吗？"


def test_collapse_repeated_period():
    assert np_("好的..") == "好的。"


def test_collapse_repeated_comma():
    assert np_("这里,,那里") == "这里，那里"


# ---------------------------------------------------------------------------
# 空格清理
# ---------------------------------------------------------------------------

def test_remove_space_between_cjk():
    assert np_("你 好 世 界") == "你好世界"


def test_remove_space_before_punct():
    assert np_("走吧 ！") == "走吧！"


# ---------------------------------------------------------------------------
# 幂等
# ---------------------------------------------------------------------------

def test_idempotent():
    samples = [
        "你好,世界.这是(注释),版本v1.2.3,数值3.14.",
        "详见 https://a.com/x,y 哦!!!真的吗??",
        "调用 f(a, b) 即可。你 好 世 界 。",
    ]
    for s in samples:
        once = np_(s)
        twice = np_(once)
        assert once == twice, f"非幂等: {once!r} -> {twice!r}"
