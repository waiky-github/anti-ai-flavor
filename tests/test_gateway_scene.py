"""网关出口接三层架构：场景自动识别 + 合规红线闸门。

这层测的是「网关真实出口行为」——`apply_flavor_hook` 走完整链路后返回什么，
而不是内部函数单独调用。四类证据：

1. 场景识别：内容判场景（营销文案 / 工程文档 / 底座兜底）
2. 合规闸门：命中字面医疗红线 → 一字不改返回原文，且不触发任何改写
3. 闸门可关：respect_compliance=False 时回落到改写链路
4. 场景可写死：cfg.scene 非 auto 时不跑识别器
"""

import asyncio

import pytest

from anti_ai_flavor import gateway_hook as flavor_hook


# 医疗宣称：真红线（功效词 + 医疗动作 + 疾病对象），长度过 min_chars=200
MEDICAL_CLAIM = (
    "这款喷雾能根治猫癣，坚持喷几天就好，猫咪不再反复发作。"
    "家里有真菌感染的猫，用它就能根治，不用去医院，也不用戴伊丽莎白圈。"
    "我家猫之前皮肤病一直不好，用了它几天就好，皮肤炎症也消了。"
) * 3

CLEAN = (
    "上周带小黑去医院，医生照了灯，说是猫癣。开了药，每天抹一次，"
    "两周后复查。整个过程花了三百多，好在不算严重。"
) * 4


def _run(coro):
    # 用 asyncio.run 而非 get_event_loop：3.12 下前者会把线程的 current loop
    # 置空，同进程内先跑过 asyncio.run 的用例会让后者抛
    # RuntimeError: There is no current event loop（实测 34 个用例连锁失败）。
    return asyncio.run(coro)


def _cfg(**over):
    base = {"enabled": True, "pass_score": 85, "min_chars": 200}
    base.update(over)
    return {"flavor_hook": base}


# ---------- 1. 场景识别 ----------

def test_detect_scene_social_note():
    """用真实发布稿（测评 fixture）验识别，不用自造短句。"""
    from pathlib import Path

    promo = Path(__file__).parent / "fixtures" / "promo_07_v9.txt"
    assert flavor_hook._detect_scene_for(
        promo.read_text(encoding="utf-8")
    ) == "social-note"


TECH_DOC = """## 修复导出接口空指针（v1.4.2）

改动集中在 `export.py` 的 `build_rows()`：补了 None 判断，新增两条 pytest 用例。

```python
def build_rows(rows):
    return [r for r in rows if r is not None]
```

灰度后 p99 延迟从 800ms 回到 120ms，错误率 0.02%。回滚验证见
`/ops/rollback/v1.4.2.md`，共 3 个步骤。"""


def test_detect_scene_tech_doc():
    assert flavor_hook._detect_scene_for(TECH_DOC) == "tech-doc"


def test_detect_scene_falls_back_to_base_on_error(monkeypatch):
    """识别器炸了必须回落 base，不能让网关发消息失败。"""
    import anti_ai_flavor.profiles.detector as detector

    def boom(*a, **kw):
        raise RuntimeError("detector down")

    monkeypatch.setattr(detector, "detect_scene", boom)
    assert flavor_hook._detect_scene_for("随便一段话") == "base"


# ---------- 2. 合规闸门 ----------

def test_compliance_hit_returns_original_without_rewrite(monkeypatch):
    """命中医疗红线：原样返回，且短语改写 / LLM 一次都不许跑。"""
    def boom(*a, **kw):
        raise AssertionError("命中合规红线后不应触发任何改写")

    monkeypatch.setattr(flavor_hook, "phrase_rewrite", boom)
    monkeypatch.setattr(flavor_hook, "_llm_rewrite_via_transport", boom)

    out = _run(flavor_hook.apply_flavor_hook(MEDICAL_CLAIM, _cfg()))
    assert out == MEDICAL_CLAIM


def test_compliance_gate_can_be_disabled(monkeypatch):
    """respect_compliance=False：闸门放行，改写链路真的跑起来。"""
    calls = {"phrase": 0}

    def fake_phrase(t):
        calls["phrase"] += 1
        return CLEAN

    monkeypatch.setattr(flavor_hook, "phrase_rewrite", fake_phrase)

    out = _run(flavor_hook.apply_flavor_hook(
        MEDICAL_CLAIM, _cfg(respect_compliance=False),
    ))
    assert calls["phrase"] == 1
    assert out != MEDICAL_CLAIM


def test_clean_text_not_blocked(monkeypatch):
    """正常宠物叙事不触发闸门（拍平负样本，防误杀）。"""
    monkeypatch.setattr(flavor_hook, "phrase_rewrite", lambda t: t)
    out = _run(flavor_hook.apply_flavor_hook(CLEAN, _cfg()))
    assert "猫癣" in out


# ---------- 3. 场景写死 ----------

def test_fixed_scene_skips_detector(monkeypatch):
    """cfg.scene 非 auto 时不跑识别器。"""
    def boom(*a, **kw):
        raise AssertionError("scene 已写死，不应调用识别器")

    monkeypatch.setattr(flavor_hook, "_detect_scene_for", boom)
    monkeypatch.setattr(flavor_hook, "phrase_rewrite", boom)

    out = _run(flavor_hook.apply_flavor_hook(
        MEDICAL_CLAIM, _cfg(scene="health-content"),
    ))
    assert out == MEDICAL_CLAIM


def test_default_config_has_scene_and_compliance():
    assert flavor_hook._DEFAULTS["scene"] == "auto"
    assert flavor_hook._DEFAULTS["respect_compliance"] is True


# ---------- 4. 跨场景兜底：识别不准也不能漏放合规 ----------

def test_medical_claim_blocked_even_if_scene_misdetected():
    """场景被识别成 base 时，合规红线仍要命中（2026-10-26 补的洞）。"""
    from anti_ai_flavor.scoring import score_text

    result = score_text(MEDICAL_CLAIM, scene="base")
    assert result.compliance_hit is True
    assert result.action == "block"
    assert "p35_medical_claim" in result.details.get("compliance_cross_scene", [])


def test_tech_metaphor_not_flagged_by_health_compliance():
    """技术文档写「根治线上抖动」不含宠物/健康领域词，不该被医疗合规则拦。"""
    from anti_ai_flavor.scoring import score_text

    text = (
        "这次改动的目标是根治线上抖动：把重试队列的退避上限从 30s 降到 5s，"
        "并把超时误判的告警规则删掉。灰度两天后 p99 从 800ms 回到 120ms。"
    )
    result = score_text(text, scene="tech-doc")
    assert result.compliance_hit is False
    assert result.action in ("pass", "warn", "rewrite")
