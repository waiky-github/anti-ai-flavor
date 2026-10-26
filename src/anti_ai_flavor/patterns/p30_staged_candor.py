"""
patterns/p30_staged_candor.py — 表演式坦诚（staged candor）

## 现象

AI 为了显得像个诚实的人，会在结论前加一句「说实话」：
「说实话，这功能我一开始也不信」「老实说，看到这句我反而信了」。

真人用这些词时通常是**转折或自我修正**，且后面跟具体内容；
AI 用它们时是**给观点加可信度标签**，删掉后句子意思不变。

## 判据

「说实话/老实说/讲真/掏心窝子/说个反常识的/恕我直言」等坦诚标记词。
单点出现只是信号（真人也会说），密集或与格言句共现才升级处置。
"""

from ._extended import ExtendedPattern

PATTERN = ExtendedPattern(
    pattern_id="p30_staged_candor",
    description="表演式坦诚：「说实话/老实说」当可信度标签用，删掉后句意不变",
    regexes=[
        r"(?:说实话|老实说|说句实话|说实在的|说句真话|说真的|讲真|不骗你|"
        r"掏心窝子|说个反常识|说个扎心的|恕我直言|不得不承认|我坦白|实不相瞒)"
    ],
    penalty=2,
    scenes=("base",),
    note="表演式坦诚（坦诚词当可信度标签）",
)

match = PATTERN.match
