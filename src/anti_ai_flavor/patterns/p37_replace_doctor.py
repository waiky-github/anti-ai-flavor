"""
patterns/p37_replace_doctor.py — 替代就医 / 与医生对比（health-content 专属）

## 现象

健康类内容的高危表述：

  「不用去医院了」「省钱不用看医生」「比医生说的还准」「医生都没看出来」

判据：免去/不用/省掉 + 就医动作；或 与医生/医院 做效果对比。
这类命中同样是合规红线，处置为 ``block``，不自动改写。
"""

from ._extended import ExtendedPattern

PATTERN = ExtendedPattern(
    pattern_id="p37_replace_doctor",
    description="替代就医 / 与医生对比：免去医院、比医生准、医生没看出来",
    regexes=[
        r"(?:不用|无需|不必|免|省)[^。！？\n]{0,6}(?:去|跑|看)(?:医院|医生|兽医|门诊)",
        r"(?:不用|无需|不必)(?:那么)?(?:麻烦|费事)[^。！？\n]{0,8}(?:医院|医生)",
        r"比(?:医生|兽医|医院)[^。！？\n]{0,10}(?:准|强|好|专业|靠谱)",
        r"(?:医生|兽医|医院)[^。！？\n]{0,8}(?:都)?(?:没|未)(?:看|查|发现|诊断)",
    ],
    penalty=10,
    scenes=("health-content",),
    note="替代就医/与医生对比（合规红线）",
)

match = PATTERN.match
