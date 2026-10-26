"""
profiles/schema.py — 场景 profile 的数据结构（2026-10-26）

## 设计立场（用户 2026-10-26 拍板）

「全场景通用 + 自动智能识别场景并切换判定」。落地成三层：

  1. 场景识别  → profiles/detector.py（阶段 2）
  2. 判定      → base 放通用指纹（底座厚），每个场景只写 delta（场景薄）
  3. 处置      → rewrite | warn | block 分档；健康合规类禁止自动改写

本文件只定义第 2、3 层的**结构**。base 见 ``profiles/base.py``，
三个场景 delta 见 ``profiles/scenes.py``。

## 为什么不把规则写进场景里

底座（p28–p37 + tier1 词表 + p01–p27）对任何场景都成立，只是权重不同。
如果每个场景复制一份规则，改一条通用规则要改四遍，必然漂移——
这正是本次要修的病灶（p01 在改写器和评分器里两套正则）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence, Tuple

# 处置动作（阶段 3 使用）
ACTION_PASS = "pass"
ACTION_WARN = "warn"
ACTION_REWRITE = "rewrite"
ACTION_BLOCK = "block"

ACTIONS = (ACTION_PASS, ACTION_WARN, ACTION_REWRITE, ACTION_BLOCK)


@dataclass(frozen=True)
class ActionPolicy:
    """分数 → 动作的分档阈值。

    语义（分数越高越干净）：

      score >= warn_at                  → pass
      rewrite_at <= score < warn_at     → warn（提示但不动手）
      block_at  <  score <  rewrite_at  → rewrite（可自动改写）
      score <= block_at                 → block（拒绝，交人工）

    合规命中（``SceneProfile.compliance_patterns``）无视分数直接 block——
    监管看的是字面，没有「分数还行」这种说法。
    """

    warn_at: int = 85
    rewrite_at: int = 70
    block_at: int = 55

    def decide(self, score: int, *, compliance_hit: bool = False) -> str:
        if compliance_hit:
            return ACTION_BLOCK
        if score <= self.block_at:
            return ACTION_BLOCK
        if score < self.rewrite_at:
            return ACTION_REWRITE
        if score < self.warn_at:
            return ACTION_WARN
        return ACTION_PASS

    def to_dict(self) -> dict:
        return {
            "warn_at": self.warn_at,
            "rewrite_at": self.rewrite_at,
            "block_at": self.block_at,
        }


@dataclass(frozen=True)
class SceneMarkers:
    """场景识别的文本特征（阶段 2 的 detector 读取这里）。

    strong：命中即视为强证据（每个 +3）
    weak：弱证据（每个 +1）
    min_score：达到多少分才算判定成功
    低置信（分数落在 0 < s < min_score 之间）时不做硬猜，交调用方追问。
    """

    strong: Sequence[str] = ()
    weak: Sequence[str] = ()
    min_score: int = 3

    def to_dict(self) -> dict:
        return {
            "strong": list(self.strong),
            "weak": list(self.weak),
            "min_score": self.min_score,
        }


@dataclass(frozen=True)
class SceneProfile:
    """一个场景的完整判定 + 处置配置。

    Attributes:
        name: 规范场景名（social-note / health-content / tech-doc / base）。
        label: 人读名称。
        description: 这个场景的语域特征，写进报告。
        aliases: 兼容旧接口的场景别名（如 coder_pr → tech-doc）。
        penalty_overrides: {pattern_id: 新罚分}，只写相对 base 的 delta。
        disabled_patterns: 本场景不适用的 pattern_id。
        extra_patterns: 场景专属 pattern_id（也在 patterns 注册表里声明了 scenes）。
        compliance_patterns: 命中即 block、永不自动改写的 pattern_id。
        policy: 分数 → 动作分档。
        markers: 场景识别特征。
        notes: 给用户看的解释。
    """

    name: str
    label: str
    description: str
    aliases: Tuple[str, ...] = ()
    penalty_overrides: Mapping[str, int] = field(default_factory=dict)
    disabled_patterns: Tuple[str, ...] = ()
    extra_patterns: Tuple[str, ...] = ()
    compliance_patterns: Tuple[str, ...] = ()
    # 本场景专属的领域词。用途：合规红线跨场景生效时的「领域闸门」——
    # 文本里没有本领域词，就不拿本场景的合规则去判它（防止技术文档里的
    # 「根治线上抖动」被当医疗宣称拦掉）。
    domain_markers: Tuple[str, ...] = ()
    policy: ActionPolicy = field(default_factory=ActionPolicy)
    markers: SceneMarkers = field(default_factory=SceneMarkers)
    notes: str = ""

    def penalty_for(self, pattern_id: str, base_penalty: int) -> int:
        """取本场景下某 pattern 的罚分（delta 覆盖，缺省沿用底座）。"""
        return self.penalty_overrides.get(pattern_id, base_penalty)

    def is_disabled(self, pattern_id: str) -> bool:
        return pattern_id in self.disabled_patterns

    def is_compliance(self, pattern_id: str) -> bool:
        return pattern_id in self.compliance_patterns

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "aliases": list(self.aliases),
            "penalty_overrides": dict(self.penalty_overrides),
            "disabled_patterns": list(self.disabled_patterns),
            "extra_patterns": list(self.extra_patterns),
            "compliance_patterns": list(self.compliance_patterns),
            "domain_markers": list(self.domain_markers),
            "policy": self.policy.to_dict(),
            "markers": self.markers.to_dict(),
            "notes": self.notes,
        }


__all__ = [
    "ACTION_PASS", "ACTION_WARN", "ACTION_REWRITE", "ACTION_BLOCK", "ACTIONS",
    "ActionPolicy", "SceneMarkers", "SceneProfile",
]
