"""
profiles/base.py — 底座 profile（全场景通用指纹）

底座厚：所有场景都跑的通用判定都在这里。
场景只写 delta（profiles/scenes.py），不复制规则——理由见 profiles/schema.py。

## 底座包含

  1. tier1 黑话词表（赋能/闭环/生态…）——rules.py
  2. legacy 检测（对称填充 / 总结收尾 / 抽象主语 / 机械排序…）
  3. p01–p27 改写型 pattern 的评分侧统计
  4. p28–p34、p36 检测型 pattern（语域味道 + 破折号 + 绝对化用语）

p35 / p37 是健康合规红线，只在 health-content 生效，不进底座。
"""

from __future__ import annotations

from .schema import ActionPolicy, SceneMarkers, SceneProfile

BASE = SceneProfile(
    name="base",
    label="通用底座",
    description=(
        "不区分场景的通用 AI 味指纹：黑话词表、空洞抽象、对仗填充、"
        "模板化枚举、格言金句、表演式坦诚、对比否定、破折号滥用、绝对化用语。"
    ),
    aliases=("default",),
    penalty_overrides={},
    disabled_patterns=(),
    extra_patterns=(),
    compliance_patterns=(),
    policy=ActionPolicy(warn_at=85, rewrite_at=70, block_at=55),
    markers=SceneMarkers(),
    notes=(
        "底座判定只覆盖「任何场景都不该出现」的表达。"
        "语域类差异（技术文档允许的枚举、口语内容允许的口气）由场景 delta 调整。"
    ),
)

__all__ = ["BASE"]
