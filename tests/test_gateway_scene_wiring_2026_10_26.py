"""网关场景接线端到端回归（2026-10-26 阶段 4）。

锁死三件事，都是「只有单测看不出、一上生产就静默降级」的接线缝：
  1. 场景识别结果必须一路传到 LLM 改写层（system prompt 带场景增量），
     否则只有评分按场景走，改写退回 base 技术口吻；
  2. 合规红线必须在进 LLM **之前**拦下——不能被「改写一下就合规了」糊过去；
  3. 显式配置的 scene 优先于自动识别（运维要能钉死口径）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from anti_ai_flavor import gateway_hook
from anti_ai_flavor.gateway_hook import (
    _detect_scene_for,
    _run_full_pipeline,
    register_llm_transport,
    resolve_flavor_config,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").strip()


class SpyTransport:
    """记录 system prompt 的假 transport；返回一段干净文本供链路采用。"""

    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list[list[dict]] = []

    async def __call__(self, messages):
        self.calls.append(messages)
        return self.reply

    @property
    def system_prompt(self) -> str:
        assert self.calls, "transport 未被调用"
        return self.calls[0][0]["content"]


@pytest.fixture
def clean_reply():
    return _fixture("promo_07_v9.txt")


@pytest.fixture(autouse=True)
def _reset_transport():
    yield
    register_llm_transport(None)


def _cfg(**overrides) -> dict:
    """构造 gateway 真实配置形状：配置挂在 gateway.flavor_hook 段下。"""
    return resolve_flavor_config({"flavor_hook": overrides})


def _run(text: str, cfg: dict) -> str:
    return asyncio.run(_run_full_pipeline(text, cfg))


def test_clean_text_never_hits_llm(clean_reply):
    """100 分的干净稿不该为评分器盲区浪费一次 LLM。"""
    spy = SpyTransport(clean_reply)
    register_llm_transport(spy)
    cfg = _cfg(enabled=True, scene="auto")
    out = _run(clean_reply, cfg)
    assert spy.calls == [], "干净文本不应进入 LLM 改写"
    assert out.strip()


def test_scene_reaches_llm_prompt(clean_reply):
    """核心回归：场景增量必须出现在 system prompt 里。"""
    spy = SpyTransport(clean_reply)
    register_llm_transport(spy)
    cfg = _cfg(enabled=True, scene="social-note")
    _run(_fixture("promo_07_v3.txt"), cfg)
    assert spy.calls, "AI 味明显的旧稿应进入 LLM 改写"
    assert "【场景覆盖：社交笔记" in spy.system_prompt


def test_health_scene_delta_reaches_prompt(clean_reply):
    spy = SpyTransport(clean_reply)
    register_llm_transport(spy)
    cfg = _cfg(enabled=True, scene="health-content")
    _run(_fixture("promo_07_v3.txt"), cfg)
    assert "【场景覆盖：健康/医疗相关文本" in spy.system_prompt


def test_tech_doc_does_not_get_social_delta(clean_reply):
    """技术文档不能被社交笔记口吻污染（反向误伤守卫）。"""
    spy = SpyTransport(clean_reply)
    register_llm_transport(spy)
    cfg = _cfg(enabled=True, scene="tech-doc")
    text = (
        "本方案通过在网关层引入自适应限流，把缓存层性能拉满后，"
        "P99 从 320ms 降到 90ms，吞吐提升 3 倍。"
    )
    _run(text, cfg)
    if spy.calls:
        assert "【场景覆盖：社交笔记" not in spy.system_prompt


def _compliance_text() -> str:
    """同时具备「AI 味要被改写」+「合规红线」的文本。

    必须两者都占，才能构成有效差验：只用纯合规短句时，这类文本本来评分就是
    100 分、根本不进 LLM，用 respect_compliance 开/关跑出来的结论会是假的。
    """
    return _fixture("promo_07_v3.txt") + "\n\n这款喷雾能根治猫癣，三天消炎。"


def test_compliance_blocks_before_llm():
    """合规红线：必须拦在 LLM 之前，一个字都不改。"""
    spy = SpyTransport(_fixture("promo_07_v9.txt"))
    register_llm_transport(spy)
    bad = _compliance_text()
    cfg = _cfg(enabled=True, scene="auto", respect_compliance=True)
    out = _run(bad, cfg)
    assert spy.calls == [], "合规命中的文本不得送进 LLM 改写"
    assert out == bad, "合规命中必须原样返回，不改写"


def test_compliance_force_allows_llm(clean_reply):
    """显式关掉 respect_compliance 才允许改写（运维兜底口子）。"""
    spy = SpyTransport(clean_reply)
    register_llm_transport(spy)
    bad = _compliance_text()
    cfg = _cfg(enabled=True, scene="auto", respect_compliance=False)
    _run(bad, cfg)
    assert spy.calls, "respect_compliance=False 时应继续走 LLM 链路"


def test_auto_scene_detects_social_note(clean_reply):
    """auto 模式下由内容判场景：v3 稿应被判为社交笔记类而非技术文档。"""
    spy = SpyTransport(clean_reply)
    register_llm_transport(spy)
    cfg = _cfg(enabled=True, scene="auto")
    v3 = _fixture("promo_07_v3.txt")
    _run(v3, cfg)
    assert spy.calls, "v3 旧稿应进入 LLM 改写"
    detected = _detect_scene_for(v3)
    assert detected in ("social-note", "health-content"), f"实际识别为 {detected}"


def test_explicit_scene_overrides_autodetect(clean_reply):
    """显式 scene 优先：即使内容像社交笔记，也按配置钉死。"""
    spy = SpyTransport(clean_reply)
    register_llm_transport(spy)
    cfg = _cfg(enabled=True, scene="tech-doc")
    _run(_fixture("promo_07_v3.txt"), cfg)
    assert spy.calls
    assert "【场景覆盖：社交笔记" not in spy.system_prompt


def test_disabled_hook_returns_original():
    bad = _fixture("promo_07_v3.txt")
    cfg = _cfg(enabled=False)
    assert _run(bad, cfg) == bad


def test_gateway_hook_public_entry_still_returns_str():
    """兼容入口契约不变：apply_flavor_hook 永远返回 str。"""
    out = asyncio.run(
        gateway_hook.apply_flavor_hook(
            _fixture("promo_07_v9.txt"), {"enabled": True, "scene": "auto"}
        )
    )
    assert isinstance(out, str) and out.strip()
