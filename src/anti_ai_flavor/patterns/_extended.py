"""
patterns/_extended.py — 检测型 pattern 公共底座（2026-10-26，场景感知改造）

## 与 p01–p27 的分工差异

  旧（p01–p27）：改写型。``match()`` 找 span，``fix()`` 直接替换成新句子，
                目标是「正则能干净洗掉」。
  新（p28+）  ：判定型。只找 span 并给罚分，**不提供 fix()**。

## 为什么这批不做自动改写

它们抓的是「语域味道」：身体反应修辞、格言金句、表演式坦诚、模板化枚举、
对比否定。这类句子的机器改写结果要么丢失人味（「我头皮麻了一下」→ 删掉），
要么换成另一种更假的说法。正确处置是交给场景策略（warn / block）或 LLM 重写，
由人拍板，而不是正则硬替换。

## 场景可见性

由 ``SceneProfile`` 控制：``scenes`` 里写 ``"base"`` 表示全场景生效；
写具体场景名（``social-note`` / ``health-content`` / ``tech-doc``）表示只在该场景生效。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

from . import Match


@dataclass(frozen=True)
class ExtendedPattern:
    """一条检测型 pattern 的声明式定义。

    Attributes:
        pattern_id: 稳定标识，会出现在 ScoreResult.hits 与报告里。
        description: 人读的一句话说明（写进文档/报告）。
        regexes: 命中正则列表，任一命中即算命中。
        penalty: 单次命中扣分（会被场景权重覆盖）。
        scenes: 可见场景；"base" = 全部场景。
        note: 命中时写进 hit 的说明。
        flags: 正则 flags，默认 0。
        min_occurrences: 最小命中次数阈值。像破折号这类「本身合法、
            密集才可疑」的特征用 >1 阈值，避免正常用法被误伤。
    """

    pattern_id: str
    description: str
    regexes: Sequence[str]
    penalty: int = 2
    scenes: Sequence[str] = ("base",)
    note: str = ""
    flags: int = 0
    min_occurrences: int = 1

    def scan(self, text: str) -> List[Match]:
        """返回所有命中的 span，按位置排序并去重（同一 span 多正则命中只留一条）。"""
        raw: List[Match] = []
        for rx in self.regexes:
            for m in re.finditer(rx, text, self.flags):
                if not m.group().strip():
                    continue
                raw.append(Match(m.start(), m.end(), m.group(), m.group()))

        seen = set()
        uniq: List[Match] = []
        for m in sorted(raw, key=lambda x: (x.start, x.end)):
            key = (m.start, m.end)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(m)

        if len(uniq) < self.min_occurrences:
            return []
        return uniq

    # p01–p27 的模块统一用 match()，这里给个同名别名，便于注册表统一调用
    def match(self, text: str) -> List[Match]:
        return self.scan(text)


__all__ = ["ExtendedPattern"]
