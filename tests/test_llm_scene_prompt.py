"""第 4 阶段收尾自测：LLM 兜底按场景切换 + CLI --scene auto 接线 — 2026-10-26

这里验证的是「真的接上了」，不是「参数存在」：

  1. LLM messages 的 system 里，非技术场景确实带上了场景覆盖段，
     技术/默认场景不带（不能污染既有简历/技术文案口吻）
  2. scene 从 llm_rewrite_async 一路透传到 transport（用注入 transport 抓 messages）
  3. CLI --scene auto 端到端：真实 v9 小红书稿 → social-note，
     技术提交说明 → tech-doc，无特征短句 → base 并打印「最像」追问提示
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"

from anti_ai_flavor.llm_rewrite import (  # noqa: E402
    SYSTEM_PROMPT,
    _build_messages,
    llm_rewrite_async,
)


def _system_for(scene: str) -> str:
    messages = _build_messages("猫背上秃了一块，我拍照传给小程序。", scene=scene)
    assert messages[0]["role"] == "system"
    return messages[0]["content"]


# ─────────────────────────────────────────────────────────────
# 1. prompt 按场景切换
# ─────────────────────────────────────────────────────────────

def test_social_note_system_prompt_overrides_tech_voice():
    system = _system_for("social-note")
    assert "场景覆盖：社交笔记" in system
    # base 技术口吻仍在，但被显式声明为可覆盖（保留既有能力，不改写 base 文案）
    assert SYSTEM_PROMPT in system
    assert "优先级高于上方" in system


def test_health_content_system_prompt_bans_medical_claims():
    system = _system_for("health-content")
    assert "场景覆盖：健康/医疗相关文本" in system
    for banned in ("根治", "消炎", "抗菌", "抗真菌", "100%"):
        assert banned in system, f"健康场景 prompt 应显式点名禁词：{banned}"
    # 不替代专业建议的措辞要保留
    assert "建议就诊" in system and "以医生为准" in system


@pytest.mark.parametrize("scene", ["default", "base", "tech-doc"])
def test_tech_scenes_keep_prompt_unchanged(scene):
    """技术场景不得混入社媒口吻，否则简历/方案文会被改成朋友圈语气。"""
    system = _system_for(scene)
    assert system == SYSTEM_PROMPT


def test_unknown_scene_falls_back_to_base_prompt():
    assert _system_for("no-such-scene") == SYSTEM_PROMPT


# ─────────────────────────────────────────────────────────────
# 2. scene 透传到 transport
# ─────────────────────────────────────────────────────────────

def test_llm_rewrite_async_passes_scene_to_transport():
    seen = []

    def fake_transport(messages):
        seen.append(messages[0]["content"])
        return "猫背上秃了一块，我拍照传给小程序，它说建议就诊。"

    import asyncio

    asyncio.run(
        llm_rewrite_async(
            "猫背上秃了一块。我拍照传给小程序，它提示建议就诊。",
            transport=fake_transport,
            scene="social-note",
            dedup=False,
        )
    )
    assert seen, "transport 没被调用"
    assert "场景覆盖：社交笔记" in seen[0]


def test_llm_rewrite_async_default_scene_no_delta():
    seen = []

    def fake_transport(messages):
        seen.append(messages[0]["content"])
        return "把导出接口的空值判断补上，加了两条用例。"

    import asyncio

    asyncio.run(
        llm_rewrite_async(
            "把导出接口的空值判断补上，加了两条用例。",
            transport=fake_transport,
            dedup=False,
        )
    )
    assert seen[0] == SYSTEM_PROMPT


# ─────────────────────────────────────────────────────────────
# 3. CLI --scene auto 端到端
# ─────────────────────────────────────────────────────────────

def _cli(*argv, stdin_text=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    env.pop("ANTI_AI_FLAVOR_LLM", None)
    return subprocess.run(
        [sys.executable, "-m", "anti_ai_flavor.cli", *argv],
        input=stdin_text if stdin_text is not None else "",
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        timeout=120,
    )


def test_cli_auto_scene_detects_social_note_on_v9():
    """真实发布稿（v9）应被识别成社交笔记，而不是 base。"""
    text = (FIXTURES / "promo_07_v9.txt").read_text(encoding="utf-8")
    proc = _cli("scene", stdin_text=text)
    assert proc.returncode == 0, proc.stderr
    assert "social-note" in proc.stdout, proc.stdout


def test_scene_subcommand_reports_confidence_and_evidence():
    text = (FIXTURES / "promo_07_v9.txt").read_text(encoding="utf-8")
    proc = _cli("scene", "--json", stdin_text=text)
    assert proc.returncode == 0, proc.stderr
    import json

    info = json.loads(proc.stdout)
    assert info["scene"] == "social-note"
    assert 0.0 <= float(info["confidence"]) <= 1.0
    assert info.get("evidence"), "识别结果必须给出证据，否则无法审计"


def test_cli_auto_scene_low_confidence_does_not_guess():
    """无足够特征 → 回落 base 且打印「最像」，绝不硬猜。"""
    proc = _cli("scene", stdin_text="今天的天气还行，下午去超市买了点东西。")
    assert proc.returncode == 0, proc.stderr
    assert "base" in proc.stdout
    # 低置信要么明确说无足够特征，要么给「最像」候选，不能静默当高置信
    assert ("无足够特征" in proc.stdout) or ("最像" in proc.stdout), proc.stdout


def test_cli_rewrite_auto_scene_smoke():
    """rewrite --scene auto 在真实稿件上跑通（不要求改写质量，只要求不崩且场景对）。"""
    text = (FIXTURES / "promo_07_v9.txt").read_text(encoding="utf-8")
    proc = _cli("rewrite", "--scene", "auto", stdin_text=text)
    assert proc.returncode == 0, proc.stderr
    assert "social-note" in (proc.stderr + proc.stdout), proc.stderr
