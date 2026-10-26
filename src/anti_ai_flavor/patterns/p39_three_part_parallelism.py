"""
patterns/p39_three_part_parallelism.py — 三段式递进排比（2026-10-26 补漏）

## 背景（验收实测漏检）

``scripts/acceptance_scene_2026_10_26.py`` 的对抗样本里，

    「它不只是掉毛，不只是皮屑，更是身体在向你发出求救信号。」

在 social-note / health-content / base 三个场景下都是 0 命中（100 分）。
通道里没有任何 pattern 抓这个骨架：

  * ``p32_template_enumeration`` 抓的是「三件事 / 第 N 点」这类**编号**枚举；
  * ``p33_contrastive_negation`` 抓的是「不是 X，**而是** Y」，要求反转落在
    「而是/都是/只是/只有」，本句落在「更是身体…」，跨不过去；
  * ``p38_vague_elevation`` 抓的升华必须落到「一种/一场/…」抽象名词，
    本句落到「身体在向你发出求救信号」，也跨不过去。

所以单独建本条，把「两次以上递进否定 + 更是」这个**结构**本身作为特征。

## 为什么这是 AI 味

人写具体经历是线性的：「上周三我扒开毛看到一块秃斑」。三段递进
（不只是 A，不只是 B，更是 C）是把观察打包成修辞格，读起来像旁白
在替读者总结意义——这正是 v3a 被判「AI 味儿很浓」的主因之一。

## 不误伤的边界

必须**两次**递进否定（不只是/不仅仅是/不仅是/不止是/不光）**都在同一句内**，
且后面接「更是」。人讲话偶尔用一个「不只是…更是…」，但那是一次递进，
本条的两次骨架密度明显更高，不拦单次。

## 处置

只判定不给 fix：删掉递进框架后句子还剩什么，取决于原话，机器改必失真。
交给场景策略（warn / rewrite / block）或 LLM 重写，由人拍板。
"""

from ._extended import ExtendedPattern

PATTERN = ExtendedPattern(
    pattern_id="p39_three_part_parallelism",
    description="三段式递进排比：不只是 A，不只是 B，更是 C（把观察打包成修辞格）",
    regexes=[
        r"(?:不只是|不仅仅是|不仅是|不止是|不光)[^。！？\n]{1,25}?[，,]\s*"
        r"(?:不只是|不仅仅是|不仅是|不止是|不光)[^。！？\n]{1,25}?[，,]\s*更是",
    ],
    penalty=3,
    scenes=("base",),
    note="三段式递进排比（AI 式修辞格）",
)

match = PATTERN.match
