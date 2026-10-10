"""flavor_hook 单测：评分放行、短文本跳过、LLM 改写、超时/异常/异常结果回退原文。

不调用真实 LLM：monkeypatch 掉评分与改写函数。
"""

import asyncio

import pytest

from anti_ai_flavor import gateway_hook as flavor_hook


LONG_NORMAL = "系统上线后运行稳定，监控指标全部正常，本周没有出现需要处理的告警。" * 5
AI_FLAVOR = "本项目全方位赋能业务闭环，深度打造数智化生态体系，持续为核心链路提供强有力的支撑。" * 6


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_disabled_returns_original():
    cfg = {"flavor_hook": {"enabled": False}}
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, cfg))
    assert out == AI_FLAVOR


def test_short_text_skipped():
    cfg = {"flavor_hook": {"enabled": True, "min_chars": 200}}
    out = _run(flavor_hook.apply_flavor_hook("短文本", cfg))
    assert out == "短文本"


def test_media_text_skipped():
    cfg = {"flavor_hook": {"enabled": True}}
    text = "MEDIA:/tmp/a.png\n" + "中文内容" * 100
    out = _run(flavor_hook.apply_flavor_hook(text, cfg))
    assert out == text


def test_rules_pass_skips_llm(monkeypatch):
    cfg = {"flavor_hook": {"enabled": True, "pass_score": 85}}

    called = {"llm": False}
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 95)

    def _boom(*a, **k):
        called["llm"] = True
        return "x"

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _boom)
    out = _run(flavor_hook.apply_flavor_hook(LONG_NORMAL, cfg))
    assert out == LONG_NORMAL
    assert called["llm"] is False


def test_low_score_triggers_llm_rewrite(monkeypatch):
    cfg = {"flavor_hook": {"enabled": True, "pass_score": 85}}
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 40)
    monkeypatch.setattr(
        flavor_hook, "_llm_rewrite_sync",
        lambda t, c: "改写后更像人话的内容，系统本周无告警，监控数据正常，值班同事没有需要跟进的事项。" * 8,
    )
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, cfg))
    assert "赋能" not in out
    assert out != AI_FLAVOR


def test_llm_exception_returns_original(monkeypatch):
    cfg = {"flavor_hook": {"enabled": True}}
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)

    def _raise(t, c):
        raise RuntimeError("LLM 不可用")

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _raise)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, cfg))
    assert out == AI_FLAVOR


def test_llm_timeout_returns_original(monkeypatch):
    cfg = {"flavor_hook": {"enabled": True, "llm_timeout": 0.01}}
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)

    def _slow(t, c):
        import time
        time.sleep(0.2)
        return t

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _slow)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, cfg))
    assert out == AI_FLAVOR


def test_bad_rewrite_result_returns_original(monkeypatch):
    cfg = {"flavor_hook": {"enabled": True}}
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    # 改写结果异常缩水
    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", lambda t, c: "太短")
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, cfg))
    assert out == AI_FLAVOR


def test_rules_scorer_failure_still_rewrites(monkeypatch):
    # 评分器异常返回 None → 按不达标处理，走 LLM
    cfg = {"flavor_hook": {"enabled": True}}
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: None)
    monkeypatch.setattr(
        flavor_hook, "_llm_rewrite_sync",
        lambda t, c: "改写后的正常内容，系统稳定运行无告警，监控面板各项指标正常，本周值班无异常。" * 8,
    )
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, cfg))
    assert out != AI_FLAVOR
