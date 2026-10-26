"""网关出口合规闸门 + 场景透传的端到端锁（2026-10-26）。

这组用例守住三件曾出问题的事：
1. ``prepare_flavor_send`` 的 min_chars 门槛会把短文本直接放行——用例必须
   构造 ≥200 字符样本，否则「合规闸门生效」的断言其实什么都没验证到
   （本轮实测踩过：54 字符样本 eligible=False，一直返回 None）。
2. 合规日志只能列真正触发合规判定的 pattern id。此前直接把全部 hits 打出来，
   日志里出现 p27_over_colloquial 等与合规无关的条目，排障会被带偏。
3. 100 分文本走网关不能被「改写」（规则层改写必须幂等）。
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from anti_ai_flavor.gateway_hook import (
    _detect_scene_for,
    _is_eligible,
    prepare_flavor_send,
    resolve_flavor_config,
    rewrite_post_send,
)

CFG = {"flavor_hook": {"enabled": True, "mode": "async_edit", "scene": "auto"}}

# 合规红线样本：不用去医院 + 比兽医还准 + 绝对化，长度 > min_chars(200)
RED_LINE = (
    "养猫的朋友都知道，猫咪皮肤出现红肿脱毛的时候，其实不用去医院，"
    "在家自己观察几天就好了。很多铲屎官一有风吹草动就往医院跑，"
    "花了钱还让猫受罪，实在没必要。\n"
    "我们这套筛查工具比兽医还准，百分百能判断皮肤病类型，"
    "绝对是每个养猫家庭的必备神器。只要上传一张照片，三秒钟就能出结果，"
    "准确率吊打市面上所有同类产品。\n"
    "我家猫当时背上秃了一块，用了三天就明显好转，效果立竿见影。"
    "相信我，这玩意儿真的值得每个人入手，赶紧点击下方链接下单吧。"
)

CLEAN = (
    "猫背上突然秃了一块，我先翻了下它的皮肤，没有破溃，只是有点皮屑。"
    "那一片大概一枚硬币大小，边缘有点发红。\n"
    "拍了张照片上传到小程序，系统给了 65/100 的提示，建议就诊。"
    "我当时还犹豫，觉得可能只是换毛。\n"
    "第三天带去医院，医生照了灯又拔毛做了镜检，确认是猫癣。"
    "开了药，也说家里要消毒，猫窝要换洗。\n"
    "现在每天按医嘱上药，那一片已经长出绒毛了。整个过程不到两周，比我想的快。\n"
    "写下来是想说，AI 只做筛查，不能替代兽医，别自己瞎猜，也别拖。\n"
    "毛孩子身上有异常，先拍照记录，再带去给医生看，比到处搜症状靠谱。\n"
)


def _run(coro):
    return asyncio.run(coro)


def test_red_line_sample_is_actually_eligible() -> None:
    """守卫本文件的前提：样本必须过 min_chars，否则后面全是空断言。"""
    cfg = resolve_flavor_config(CFG)
    assert len(RED_LINE) >= int(cfg["min_chars"])
    assert _is_eligible(RED_LINE, int(cfg["min_chars"]))
    assert _is_eligible(CLEAN, int(cfg["min_chars"]))


def test_gateway_blocks_rewrite_on_compliance() -> None:
    """合规红线命中时网关不改写，原样发出（返回 None 表示无需替换）。"""
    out = _run(rewrite_post_send(RED_LINE, CFG))
    assert out is None


def test_compliance_log_lists_only_compliance_patterns(caplog) -> None:
    """日志里不许出现与合规无关的 pattern id（如 p27_over_colloquial）。"""
    with caplog.at_level(logging.WARNING, logger="anti_ai_flavor.gateway_hook"):
        _run(rewrite_post_send(RED_LINE, CFG))
    msgs = [r.getMessage() for r in caplog.records if "合规红线命中" in r.getMessage()]
    assert msgs, "合规闸门未触发，样本或门槛失效"
    line = msgs[0]
    assert "p35_medical_claim" in line or "p37_replace_doctor" in line
    assert "p27_over_colloquial" not in line


def test_scene_detected_on_gateway_path() -> None:
    """网关场景识别跑通，宠物健康叙事归到 health-content（更严的场景）。

    这条是实测结论而非假设：含「猫/癣/兽医/毛孩子」的叙事文本会被判
    health-content 而不是 social-note，因此 p35/p37 合规则全程生效。
    发布前闸门要的正是这个更严的口径。
    """
    assert _detect_scene_for(CLEAN) == "health-content"


def test_prepare_send_never_blocks_and_returns_original() -> None:
    """async_edit 模式下发送前必须毫秒返回原文，不阻塞。"""
    send, pending = _run(prepare_flavor_send(CLEAN, CFG))
    assert send == CLEAN
    assert pending == CLEAN


@pytest.mark.parametrize("text", [CLEAN, RED_LINE])
def test_disabled_hook_is_noop(text: str) -> None:
    cfg = {"flavor_hook": {"enabled": False}}
    out = _run(rewrite_post_send(text, cfg))
    assert out is None
