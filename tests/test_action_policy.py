"""动作分级（三层架构第 3 层）自测 — 2026-10-26

验证「同一段文字，在不同场景下的处置动作不同」，以及动作确实被 CLI 执行
（不是只算出来写在报告里）。

四类证据：

  1. ActionPolicy 分档边界（pass / warn / rewrite / block 四个档位的临界值）
  2. 场景差异：医疗功效宣称在 health-content 是合规 block，在 social-note 不是
  3. 误杀回归：「有效提升工作效率」这类普通文案不算医疗宣称
  4. CLI e2e：合规命中拒绝改写（退出码 2）、--force 放行、--gate 三档退出码、
     非 gate 的 block 仍输出改写但要求人工复核
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from anti_ai_flavor.profiles import resolve_profile
from anti_ai_flavor.profiles.schema import ActionPolicy
from anti_ai_flavor.scoring import score_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"

# 供 CLI 端到端调用的固定样本
MEDICAL_CLAIM = "这个功能能治猫癣，三天消炎，抗菌除螨。"
FALSE_POSITIVE = "通过系统化的方法，我们能够有效提升整体的工作效率，同时形成良好的协作机制。"
DIRTY_TEXT = "在当今快速发展的时代，我们需要深入探讨这一系统性议题，形成闭环，持续赋能，全方位提升。"
CLEAN_TEXT = "猫背上秃了一块。我拍照传给小程序，它提示建议就诊。去医院照灯，医生说是猫藓，按医嘱抹药一周就好了。"

# warn 档样本：长度 740 字的平实文本 + 两个「由此可见」，raw=6 → score≈71
NEUTRAL = "今天给它换了猫砂，它闻了半天才进去。"
WARN_TEXT = NEUTRAL * 40 + "由此可见，方案可行。" + "由此可见，结论一致。"


def _cli(*argv, stdin_text=None):
    """以子进程方式跑真实 CLI，返回 CompletedProcess（含 exit_code/stderr）。"""
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


# ─────────────────────────────────────────────────────────────
# 1. 分档边界
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "score,expected",
    [
        (100, "pass"),
        (86, "pass"),
        (85, "pass"),    # warn_at=85：分数 >= 85 视为干净
        (84, "warn"),
        (71, "warn"),
        (70, "warn"),    # rewrite_at=70：70 <= score < 85 只警告
        (69, "rewrite"),
        (56, "rewrite"),  # block_at=55：55 < score < 70 可自动改写
        (55, "block"),   # 边界含等号：score <= block_at 即 block
        (54, "block"),
        (0, "block"),
    ],
)
def test_action_policy_boundaries(score, expected):
    assert ActionPolicy(warn_at=85, rewrite_at=70, block_at=55).decide(score) == expected


def test_compliance_overrides_every_score():
    """合规命中无视分数：这是监管字面问题，不存在「分数还行」。"""
    policy = ActionPolicy(warn_at=85, rewrite_at=70, block_at=55)
    for score in (100, 95, 85, 70, 0):
        assert policy.decide(score, compliance_hit=True) == "block"


# ─────────────────────────────────────────────────────────────
# 2. 同一段文字，场景不同 → 动作不同
# ─────────────────────────────────────────────────────────────

def test_medical_claim_blocks_in_health_content():
    result = score_text(MEDICAL_CLAIM, scene="health-content")
    assert result.compliance_hit is True
    assert result.action == "block"
    assert any(h.pattern_id == "p35_medical_claim" for h in result.hits)


def test_medical_claim_still_compliance_in_social_note():
    """小红书笔记写「能治猫癣」照样是合规红线（2026-10-26 改口径）。

    旧口径按场景挂合规：social-note 下不判 p35。结果是小宠物健康类笔记
    （正是本项目的主场景）把功效宣称整段放过去了——识别成 social-note
    就等于免检，等于闸门在最该拦的地方失效。
    新口径：只要文本在健康领域（domain_markers 命中），合规则跨场景生效。
    """
    result = score_text(MEDICAL_CLAIM, scene="social-note")
    assert result.compliance_hit is True
    assert result.action == "block"
    assert "p35_medical_claim" in result.details.get("compliance_cross_scene", [])


def test_medical_word_outside_health_domain_not_compliance():
    """领域闸门：技术文档写「根治线上抖动」不含健康领域词，不判合规。"""
    text = "这次改动的目标是根治线上抖动，把重试队列退避上限从 30s 降到 5s。"
    result = score_text(text, scene="tech-doc")
    assert result.compliance_hit is False


def test_policy_thresholds_differ_by_scene():
    social = resolve_profile("social-note").policy
    health = resolve_profile("health-content").policy
    summary = "哎呀好可爱的一天".ljust(30, "呀")
    # 同一分数在健康内容里更严：health 的 rewrite_at 比 social 高
    assert health.rewrite_at > social.rewrite_at
    assert health.block_at > social.block_at
    assert score_text(summary, scene="health-content").score == 100


# ─────────────────────────────────────────────────────────────
# 3. 误杀回归
# ─────────────────────────────────────────────────────────────

def test_effectiveness_word_alone_is_not_medical_claim():
    """「有效」单独出现（有效提升效率）不是医疗宣称，不能误判合规红线。"""
    result = score_text(FALSE_POSITIVE, scene="health-content")
    assert result.compliance_hit is False


@pytest.mark.parametrize(
    "text",
    [
        "每天抹一次，有效缓解瘙痒。",
        "对猫癣特别有效。",
        "这个办法有效预防皮肤感染。",
    ],
)
def test_real_medical_claims_still_caught(text):
    assert score_text(text, scene="health-content").compliance_hit is True


# ─────────────────────────────────────────────────────────────
# 4. CLI 端到端：动作真的被执行
# ─────────────────────────────────────────────────────────────

def test_cli_refuses_to_rewrite_compliance_hit():
    proc = _cli("rewrite", "--scene", "health-content", stdin_text=MEDICAL_CLAIM)
    assert proc.returncode == 2, proc.stderr
    assert "合规红线" in proc.stderr
    assert proc.stdout.strip() == "", "拒绝改写时不允许把改写结果打到 stdout"


def test_cli_force_overrides_compliance_refusal():
    proc = _cli("rewrite", "--scene", "health-content", "--force", stdin_text=MEDICAL_CLAIM)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() != ""


def test_cli_health_claim_blocked_in_social_note():
    """端到端：健康功效宣称在小红书场景也拒绝改写（退出码 2）。"""
    proc = _cli("rewrite", "--scene", "social-note", stdin_text=MEDICAL_CLAIM)
    assert proc.returncode == 2, proc.stderr
    assert "p35_medical_claim" in proc.stderr, proc.stderr
    assert proc.stdout.strip() == ""


def test_cli_non_health_text_allowed_in_social_note():
    """换领域就放行：不含健康领域词的「根治」比喻不被当合规红线。"""
    proc = _cli(
        "rewrite", "--scene", "social-note",
        stdin_text="这次改动的目标是根治线上抖动，把重试队列上限从 30s 降到 5s。",
    )
    assert proc.returncode == 0, proc.stderr


def test_cli_gate_blocks_dirty_text():
    proc = _cli("rewrite", "--scene", "social-note", "--gate", stdin_text=DIRTY_TEXT)
    assert proc.returncode == 2, proc.stderr
    assert "block" in proc.stderr


def test_cli_gate_warns_mid_text():
    proc = _cli("rewrite", "--scene", "social-note", "--gate", stdin_text=WARN_TEXT)
    assert proc.returncode == 1, proc.stderr
    assert "warn" in proc.stderr
    assert proc.stdout.strip() == "", "warn 档不应输出改写结果"


def test_cli_gate_passes_clean_text():
    proc = _cli("rewrite", "--scene", "social-note", "--gate", stdin_text=CLEAN_TEXT)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() != ""


def test_cli_non_gate_block_still_rewrites_but_warns():
    """非闸门模式下 block 档仍然给结果（用户要的是改写稿），但必须提示人工复核。"""
    proc = _cli("rewrite", "--scene", "social-note", stdin_text=DIRTY_TEXT)
    assert proc.returncode == 0, proc.stderr
    assert "仅供参考" in proc.stderr
    assert proc.stdout.strip() != ""


def test_cli_report_carries_scene_and_action():
    proc = _cli("rewrite", "--scene", "social-note", "--report", stdin_text=DIRTY_TEXT)
    assert proc.returncode == 0, proc.stderr
    import json

    payload = json.loads(proc.stdout)
    assert payload["scene"] == "social-note"
    assert payload["action"] == "block"
    assert payload["compliance_hit"] is False


def test_cli_scene_subcommand_reports_policy():
    proc = _cli("scene", stdin_text=CLEAN_TEXT)
    assert proc.returncode == 0, proc.stderr
    assert "动作分档" in proc.stdout
