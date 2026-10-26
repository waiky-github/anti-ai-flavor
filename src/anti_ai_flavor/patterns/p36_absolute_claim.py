"""
patterns/p36_absolute_claim.py — 绝对化用语（全场景 base + health 加权）

## 现象

广告法禁用的绝对化表述：「最好的」「第一」「100%」「唯一」「必备」。

## 为什么不误伤

- 序数：「第一次」「第一步」「第一批」是序数，不是绝对化 → 排除。
- 数据库术语：「唯一索引」「唯一约束」→ 排除。
- 建议语气：「最好先问医生」是建议，不是宣称 → 只认「最好的/最好用/最好选」。
"""

from ._extended import ExtendedPattern

PATTERN = ExtendedPattern(
    pattern_id="p36_absolute_claim",
    description="绝对化用语：最好的/第一/100%/唯一/必备（排除序数与数据库术语、建议语气）",
    regexes=[
        r"最好(?:的|用|选)",
        r"第一(?!次|步|眼|天|时间|批|版|个|章|节|行|轮|阶段|部分)",
        r"(?:100\s*%|百分之百)",
        r"唯一(?!索引|约束|键|标识|值)",
        r"(?:必备|必选|必买)",
    ],
    penalty=4,
    scenes=("base",),
    note="绝对化用语",
    min_occurrences=1,
)

match = PATTERN.match
