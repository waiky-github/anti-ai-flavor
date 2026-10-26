"""
patterns/p34_em_dash_abuse.py — 破折号滥用（补 detector 的漏网）

## 背景（2026-10-26 修 bug）

``detectors.detect_em_dash`` 只认 ``EM_DASH_OVERUSE``（要求连续 2 个以上破折号），
而 AI 最典型的破折号用法是**单个 em dash 夹在汉字之间当插入语**
（「不是因为它便宜—而是因为它有效」），这种一命中都抓不到。
``scoring`` 更是完全没有破折号规则。

## 判据（分两档，避免误伤正常中文）

1. 单破折号夹在汉字之间（U+2014 / U+2013）——中文标点里不该出现，直接可疑。
2. 成对双破折号插入语、连续 3 个以上破折号——中文里合规但密集才可疑，
   故要求 ``min_occurrences=2``。

正文里出现「——」一次属正常中文书写，不扣分。
"""

from ._extended import ExtendedPattern

PATTERN = ExtendedPattern(
    pattern_id="p34_em_dash_abuse",
    description="破折号滥用：单 em dash 夹汉字作插入语，或成对/连续破折号密集出现",
    regexes=[
        # 单破折号夹在汉字之间（中文里不合规）
        r"[\u4e00-\u9fff][—–][\u4e00-\u9fff]",
        # 连续 3 个以上破折号
        r"—{3,}",
        # 成对双破折号插入语
        r"—{2}[^—\n]{1,40}—{2}",
        # 英文习惯的前后空格单破折号
        r"\s—\s",
    ],
    penalty=3,
    scenes=("base",),
    note="破折号滥用",
    min_occurrences=2,
)

match = PATTERN.match
