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


@pytest.fixture(autouse=True)
def _reset_injected_transport():
    """每个用例前后清空模块级注入 transport，防止全局状态串扰。"""
    flavor_hook.register_llm_transport(None)
    yield
    flavor_hook.register_llm_transport(None)


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


def test_phrase_rewrite_pass_skips_llm(monkeypatch):
    # 原文低分；短语改写产物高分 → 采用产物，不调 LLM
    from anti_ai_flavor.phrase_rewrite import phrase_rewrite as real_pr
    clean = "系统本周稳定，无告警，监控正常，值班无需跟进。" * 6

    def fake_phrase(t):
        return clean if t != clean else t

    monkeypatch.setattr(flavor_hook, "phrase_rewrite", fake_phrase)

    def _score(t):
        return 40 if t != clean else 95

    monkeypatch.setattr(flavor_hook, "_rules_score", _score)
    called = {"llm": False}

    def _boom(*a, **k):
        called["llm"] = True
        return "x"

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _boom)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == clean
    assert called["llm"] is False


# ---------- 进入 LLM 的各路径 ----------

def test_phrase_no_change_then_llm(monkeypatch):
    # 短语改写无命中（返回原文）→ LLM，喂原文，key 被传入
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 40)
    monkeypatch.setattr(flavor_hook, "phrase_rewrite", lambda t: t)

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


def test_phrase_still_low_feeds_phrase_output_to_llm(monkeypatch):
    # 短语有产物但仍低分 → LLM，喂短语产物
    _force_key(monkeypatch)
    partial = "部分清洗后仍有残留味道的内容。" * 6
    monkeypatch.setattr(flavor_hook, "phrase_rewrite", lambda t: partial)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 40)

    seen = {"input": None}

    def _llm(text, c, key):
        seen["input"] = text
        return LLM_CLEAN

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _llm)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == LLM_CLEAN
    assert seen["input"] == partial


def test_phrase_failure_then_llm_uses_original(monkeypatch):
    # 短语改写抛异常 → 回原文喂 LLM
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 40)

    def _boom_phrase(t):
        raise RuntimeError("phrase engine error")

    monkeypatch.setattr(flavor_hook, "phrase_rewrite", _boom_phrase)
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


# ---------- 受保护内容校验 ----------

def test_llm_corrupts_version_returns_original(monkeypatch):
    # 原文含版本号 v1.2.3；LLM 把它读成 v14 → 校验失败，回退规范化原文
    _force_key(monkeypatch)
    base = "我们需要升级核心模块，版本号 v1.2.3 必须保留，请全方位赋能业务闭环。" * 12
    assert len(base) >= 200
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)
    # LLM 返回里版本号被破坏
    monkeypatch.setattr(
        flavor_hook, "_llm_rewrite_sync",
        lambda t, c, key: "我们需要升级模块，版本号 v14 请保留。" * 12,
    )
    out = _run(flavor_hook.apply_flavor_hook(base, _cfg()))
    # 回退的是规范化原文（v1.2.3 完好）
    assert "v1.2.3" in out
    assert "v14" not in out


def test_llm_preserves_token_adopts_rewrite(monkeypatch):
    # LLM 改写后版本号逐字保留、内容达标 → 采用
    _force_key(monkeypatch)
    base = "我们需要升级核心模块，版本号 v1.2.3 必须保留，请全方位赋能业务闭环。" * 12
    assert len(base) >= 200
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)

    def _score(t):
        # 原文低分，改写产物高分
        return 30 if "赋能" in t else 90

    monkeypatch.setattr(flavor_hook, "_rules_score", _score)
    clean = "升级核心模块时，版本号 v1.2.3 保持不变，直接沿用即可。" * 12
    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", lambda t, c, key: clean)
    out = _run(flavor_hook.apply_flavor_hook(base, _cfg()))
    assert "v1.2.3" in out
    assert "赋能" not in out


def test_no_auto_space_between_cjk_and_alnum():
    # 用户拍板：中英文/数字之间不自动加空格（2026-10-10）
    from anti_ai_flavor.core import rewrite_text
    s = "用Python开发共3个模块，调用API耗时30秒，" * 6
    out = rewrite_text(s)
    assert "用 Python" not in out
    assert "共 3" not in out
    assert "用Python" in out


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


# —— LLM 空返回重试 ——

def test_llm_empty_thinking_retries_then_succeeds(monkeypatch):
    """前两次只输出 thinking（空），第三次成功 → 返回成功结果，共调用 3 次。"""
    import importlib
    lr = importlib.import_module("anti_ai_flavor.llm_rewrite")
    calls = {"n": 0}

    def _fake_rewrite(text, *, api_key, max_chunk_chars):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("LLM rewrite 剥离 thinking 块后为空")
        return "改写成功的干净正文内容"

    monkeypatch.setattr(lr, "llm_rewrite", _fake_rewrite)
    out = flavor_hook._llm_rewrite_sync("黑话原文", 1500, "key")
    assert out == "改写成功的干净正文内容"
    assert calls["n"] == 3


def test_llm_empty_thinking_all_fail_raises(monkeypatch):
    """连续 3 次都只输出 thinking → 重试耗尽，抛出原错误。"""
    import importlib
    import pytest
    lr = importlib.import_module("anti_ai_flavor.llm_rewrite")
    calls = {"n": 0}

    def _fake_rewrite(text, *, api_key, max_chunk_chars):
        calls["n"] += 1
        raise RuntimeError("LLM rewrite 剥离 thinking 块后为空")

    monkeypatch.setattr(lr, "llm_rewrite", _fake_rewrite)
    with pytest.raises(RuntimeError, match="剥离 thinking 块后为空"):
        flavor_hook._llm_rewrite_sync("黑话原文", 1500, "key")
    assert calls["n"] == 3


def test_llm_other_runtime_error_not_retried(monkeypatch):
    """非「空 thinking」的 RuntimeError 立即上抛，不重试。"""
    import importlib
    import pytest
    lr = importlib.import_module("anti_ai_flavor.llm_rewrite")
    calls = {"n": 0}

    def _fake_rewrite(text, *, api_key, max_chunk_chars):
        calls["n"] += 1
        raise RuntimeError("鉴权失败 401")

    monkeypatch.setattr(lr, "llm_rewrite", _fake_rewrite)
    with pytest.raises(RuntimeError, match="鉴权失败 401"):
        flavor_hook._llm_rewrite_sync("黑话原文", 1500, "key")
    assert calls["n"] == 1


# ---------- 注入 transport（宿主通道） ----------

def test_register_and_get_transport():
    def t(messages):
        return "x"

    flavor_hook.register_llm_transport(t)
    assert flavor_hook.get_registered_llm_transport() is t
    flavor_hook.register_llm_transport(None)
    assert flavor_hook.get_registered_llm_transport() is None


def test_injected_async_transport_used_without_key(monkeypatch):
    # 注册 async transport 后：不解析 key、不走直连线程；transport 收到 messages。
    key_called = {"n": False}
    monkeypatch.setattr(
        flavor_hook, "_resolve_api_key",
        lambda: key_called.__setitem__("n", True) or "should-not-be-used",
    )
    sync_called = {"n": False}
    monkeypatch.setattr(
        flavor_hook, "_llm_rewrite_sync",
        lambda *a, **k: sync_called.__setitem__("n", True) or "x",
    )

    seen = {"messages": None, "calls": 0}

    async def _transport(messages):
        seen["calls"] += 1
        seen["messages"] = messages
        return LLM_CLEAN

    flavor_hook.register_llm_transport(_transport)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)

    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == LLM_CLEAN
    assert seen["calls"] == 1
    assert key_called["n"] is False
    assert sync_called["n"] is False
    # messages 为 system + user 两条
    assert isinstance(seen["messages"], list)
    assert seen["messages"][0]["role"] == "system"
    assert seen["messages"][1]["role"] == "user"


def test_injected_sync_transport_also_supported(monkeypatch):
    # 注入的 transport 也可以是同步 callable（返回 str），透明 await。
    flavor_hook.register_llm_transport(lambda messages: LLM_CLEAN)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == LLM_CLEAN


def test_injected_transport_exception_returns_original(monkeypatch):
    async def _boom(messages):
        raise RuntimeError("auxiliary provider 全挂了")

    flavor_hook.register_llm_transport(_boom)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == AI_FLAVOR


def test_injected_transport_timeout_returns_original(monkeypatch):
    async def _slow(messages):
        await asyncio.sleep(0.2)
        return LLM_CLEAN

    flavor_hook.register_llm_transport(_slow)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg(llm_timeout=0.01)))
    assert out == AI_FLAVOR


def test_injected_transport_empty_thinking_retries(monkeypatch):
    # 经注入通道，模型前两次只给 thinking（剥后为空），第三次成功。
    calls = {"n": 0}

    def _transport(messages):
        calls["n"] += 1
        if calls["n"] < 3:
            # 含 think 块且剥后为空 → llm_rewrite_async 抛「剥离 thinking 块后为空」
            return "<think>模型只在思考</think>   "
        return LLM_CLEAN

    flavor_hook.register_llm_transport(_transport)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 30)
    monkeypatch.setattr(flavor_hook, "_rules_rewrite", lambda t: t)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == LLM_CLEAN
    assert calls["n"] == 3


def test_no_transport_falls_back_to_direct_key_path(monkeypatch):
    # 未注册 transport 时，行为退回旧版：解析 key + 线程池直连。
    assert flavor_hook.get_registered_llm_transport() is None
    _force_key(monkeypatch)
    monkeypatch.setattr(flavor_hook, "_rules_score", lambda t: 40)
    monkeypatch.setattr(flavor_hook, "phrase_rewrite", lambda t: t)
    seen = {}

    def _llm(text, c, key):
        seen["key"] = key
        return LLM_CLEAN

    monkeypatch.setattr(flavor_hook, "_llm_rewrite_sync", _llm)
    out = _run(flavor_hook.apply_flavor_hook(AI_FLAVOR, _cfg()))
    assert out == LLM_CLEAN
    assert seen["key"] == "test-secret-key"
