"""flavor_hook 单测：评分放行 / rules 改写 / LLM 兜底 / key 解析 /
超时异常异常结果回退原文。

不调用真实 LLM / 真实 rules：monkeypatch 掉评分、rules 改写、key 解析与 LLM 改写。
"""

import asyncio

import pytest

from anti_ai_flavor import gateway_hook as flavor_hook


LONG_NORMAL = "系统上线后运行稳定，监控指标全部正常，本周没有需要处理的告警。" * 5
AI_FLAVOR = "本项目全方位赋能业务闭环，深度打造数智化生态体系，持续为核心链路提供强有力的支撑。" * 6

RULES_CLEAN = "改写后更像人话的内容，系统本周无告警，监控数据正常，值班同事没有需要跟进的事项。" * 8
LLM_CLEAN = "LLM 重写后的内容，系统稳定运行无告警，监控面板各项指标正常，本周值班无异常。" * 8


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _cfg(**over):
    base = {"enabled": True, "pass_score": 85}
    base.update(over)
    return {"flavor_hook": base}


def _force_key(monkeypatch, key="test-secret-key"):
    """让主链路认为解析到了可用 LLM key。"""
    monkeypatch.setattr(flavor_hook, "_resolve_api_key", lambda: key)


# ---------- 资格 / 开关 ----------

def test_disabled_returns_original():
    cfg = {"flavor_hook": {"enabled": False}}
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, cfg))
    assert out == AI_FLAVOR


def test_short_text_skipped():
    out = _run(flavor_hook.apply_flavor_hook("短文本", _cfg(min_chars=200)))
    assert out == "短文本"


def test_media_text_skipped():
    text = "MEDIA:/tmp/a.png\n" + "中文内容" * 100
    out = _run(flavor_hook.apply_flavor_hook(text, _cfg()))
    assert out == text


# ---------- rules 放行 / rules 改写 ----------

def test_rules_pass_skips_everything(monkeypatch):
    # 原文高分 → rules 改写和 LLM 都不该被调用
    called = {"rules": False, "llm": False}
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 95)
    monkeypatch.setattr(
        flavor_hook, "_rules_rewrite",
        lambda t: called.__setitem__("rules", True) or t,
    )

    def _boom(*a, **k):
        called["llm"] = True
        return "x"

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _boom)
    out = _run(flavor_hook.apply_flavor_hook(LONG_NORMAL, _cfg()))
    assert out == LONG_NORMAL
    assert called == {"rules": False, "llm": False}


def test_rules_rewrite_pass_skips_llm(monkeypatch):
    # 原文低分；rules 改写产物高分 → 采用 rules 产物，不调 LLM
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: RULES_CLEAN)

    def _score(t):
        return 40 if t == AI_FLAVOR else 95

    monkeypatch.setattr(flavor_hook, "_rules_score", _score)
    called = {"llm": False}

    def _boom(*a, **k):
        called["llm"] = True
        return "x"

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _boom)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == RULES_CLEAN
    assert called["llm"] is False


# ---------- 进入 LLM 的各路径 ----------

def test_rules_rewrite_no_change_then_llm(monkeypatch):
    # rules 改写无实质变化（返回原文）→ LLM，喂原文，key 被传入
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 40)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)

    seen = {}

    def _llm(text, c, key):
        seen["input"] = text
        seen["key"] = key
        return LLM_CLEAN

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _llm)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == LLM_CLEAN
    assert seen["input"] == AI_FLAVOR
    assert seen["key"] == "test-secret-key"


def test_rules_rewrite_still_low_feeds_rules_output_to_llm(monkeypatch):
    # rules 有产物但仍低分 → LLM，喂 rules 产物
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: RULES_CLEAN)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 40)

    seen = {"input": None}

    def _llm(text, c, key):
        seen["input"] = text
        return LLM_CLEAN

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _llm)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == LLM_CLEAN
    assert seen["input"] == RULES_CLEAN


def test_rules_rewrite_failure_then_llm_uses_original(monkeypatch):
    # rules 改写返回 None → LLM 用原文
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 40)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: None)

    seen = {"input": None}

    def _llm(text, c, key):
        seen["input"] = text
        return LLM_CLEAN

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _llm)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == LLM_CLEAN
    assert seen["input"] == AI_FLAVOR


def test_llm_exception_returns_original(monkeypatch):
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)

    def _raise(text, c, key):
        raise RuntimeError("LLM 不可用")

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _raise)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == AI_FLAVOR


def test_llm_timeout_returns_original(monkeypatch):
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)

    def _slow(text, c, key):
        import time
        time.sleep(0.2)
        return text

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _slow)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg(llm_timeout=0.01)))
    assert out == AI_FLAVOR


def test_bad_llm_result_returns_original(monkeypatch):
    # LLM 结果异常缩水 → 发原文
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)
    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", lambda t, c, key: "太短")
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == AI_FLAVOR


def test_scorer_failure_rules_then_llm(monkeypatch):
    # 评分器异常返回 None（原文按不达标处理）→ rules 无变化 → 走 LLM
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: None)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)
    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", lambda t, c, key: LLM_CLEAN)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == LLM_CLEAN


def test_no_resolved_key_returns_original(monkeypatch):
    # key 解析不到 → 直接发原文，不调 LLM
    monkeypatch.setattr(flavor_hook, "_resolve_api_key", lambda: None)
    called = {"llm": False}
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)

    def _llm(*a, **k):
        called["llm"] = True
        return LLM_CLEAN

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _llm)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == AI_FLAVOR
    assert called["llm"] is False


# ---------- key 解析 ----------

def test_valid_key_helper():
    assert flavor_hook._valid_key("sk-real-value")
    assert not flavor_hook._valid_key("")
    assert not flavor_hook._valid_key(None)
    assert not flavor_hook._valid_key("${MINIMAX_CN_API_KEY}")
    assert not flavor_hook._valid_key("$SOMETHING")


def test_resolve_api_key_prefers_valid_env(monkeypatch):
    monkeypatch.setenv("ANTI_AI_LLM_API_KEY", "sk-from-env-123")
    assert flavor_hook._resolve_api_key() == "sk-from-env-123"


def test_resolve_api_key_literal_env_falls_back_to_env_file(monkeypatch):
    # env 是未展开字面量 → 回 .env 文件读
    monkeypatch.setenv("ANTI_AI_LLM_API_KEY", "${MINIMAX_CN_API_KEY}")
    monkeypatch.setattr(
        flavor_hook, "_read_env_file_key", lambda name: "sk-from-file-456",
    )
    assert flavor_hook._resolve_api_key() == "sk-from-file-456"


def test_resolve_api_key_all_invalid_returns_none(monkeypatch):
    monkeypatch.setenv("ANTI_AI_LLM_API_KEY", "${MINIMAX_CN_API_KEY}")
    monkeypatch.setattr(flavor_hook, "_read_env_file_key", lambda name: None)
    assert flavor_hook._resolve_api_key() is None
