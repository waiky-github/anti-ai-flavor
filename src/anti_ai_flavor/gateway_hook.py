"""
Flavor hook — gateway 回复发出前自动检测并清洗「AI 味儿」。

在普通消息路径（非 slash 命令、非 streaming）handler 返回文本后调用：
  1. 只处理纯中文文本（无 MEDIA:/图片/附件标记），长度达阈值；
  2. rules-only score_text 毫秒检测，分数达标直接放行，不烧 token；
  3. 不达标 → 先跑纯 rules rewrite_text，改写后再评分，达标即发（0 token）；
  4. rules 改写后仍不达标（或没实质变化）→ 线程池跑 llm_rewrite（MiniMax-M3 默认），带超时；
  5. 任何异常 / 超时 / 改写结果异常 → 原样返回，绝不能因为本 hook 吞掉回复。

配置（gateway config，均有默认值）：
    gateway:
      flavor_hook:
        enabled: false          # 总开关，验证通过后手工打开
        min_chars: 200          # 低于该长度不处理
        pass_score: 85          # rules 分数 ≥ 该值放行
        llm_timeout: 90         # LLM 改写超时秒数
        llm_max_chunk_chars: 1500

硬约束：本模块对调用方承诺「拿不回更好的文本，就拿回原文」。
"""

import asyncio
import logging
import os
import re
from typing import Any, Dict, Optional

from anti_ai_flavor.punctuation import (
    normalize_punctuation,
    protected_tokens_preserved,
)

logger = logging.getLogger(__name__)

# 含这些内容的回复不处理（媒体/附件/内部指令），交给平台原有的媒体投递逻辑
_SKIP_MARKERS = ("MEDIA:", "[[as_document]]", "[[audio_as_voice]]")
# markdown 图片 / HTML 图片
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<img\s", re.IGNORECASE)
# 中文字符
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "min_chars": 200,
    "pass_score": 85,
    "llm_timeout": 90,
    "llm_max_chunk_chars": 1500,
    "min_keep_chars": 80,
}


def _load_config_yaml() -> Dict[str, Any]:
    """读取当前 profile 的 config.yaml，失败返回 {}。

    独立实现，避免 platforms/base.py 反向依赖 gateway/run.py。
    """
    try:
        import yaml
        from hermes_cli.config import get_hermes_home
        path = get_hermes_home() / "config.yaml"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception as exc:
        logger.debug("flavor_hook: 读取 config.yaml 失败: %s", exc)
    return {}


def resolve_flavor_config(gateway_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从 gateway config 解析 flavor_hook 配置，缺省值兜底。

    gateway_config 为 None 时自行从 config.yaml 的 gateway 节读取。
    """
    cfg = dict(_DEFAULTS)
    if gateway_config is None:
        root = _load_config_yaml()
        gateway_config = root.get("gateway") if isinstance(root, dict) else None
    if isinstance(gateway_config, dict):
        section = gateway_config.get("flavor_hook")
        if isinstance(section, dict):
            for key in _DEFAULTS:
                if key in section and section[key] is not None:
                    cfg[key] = section[key]
    return cfg


def _is_eligible(text: str, min_chars: int) -> bool:
    """判断回复是否适合过 flavor：纯文本、中文为主、长度达阈值。"""
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < min_chars:
        return False
    for marker in _SKIP_MARKERS:
        if marker in stripped:
            return False
    if _IMAGE_RE.search(stripped):
        return False
    # 中文字符数需达到长度的 30%，避免中英混合/纯英文文本被中文规则处理
    cjk_count = len(_CJK_RE.findall(stripped))
    return cjk_count >= max(20, int(len(stripped) * 0.3))


def _rules_score(text: str) -> Optional[int]:
    """rules-only 评分；导入失败/异常返回 None（调用方按放行处理）。"""
    try:
        from anti_ai_flavor.scoring import score_text
        result = score_text(text)
        score = getattr(result, "score", None)
        return int(score) if score is not None else None
    except Exception as exc:
        logger.warning("flavor_hook: rules 评分失败，放行原文: %s", exc)
        return None


def _rules_rewrite(text: str) -> Optional[str]:
    """纯 rules 改写（0 token）。导入失败/异常返回 None。"""
    try:
        from anti_ai_flavor.core import rewrite_text
        return rewrite_text(text)
    except Exception as exc:
        logger.warning("flavor_hook: rules 改写失败: %s", exc)
        return None


def _valid_key(v: Optional[str]) -> bool:
    """判断 key 是否为可用真值：非空、不是未展开的 ${VAR} 字面量。"""
    return bool(v) and "${" not in v and not v.startswith("$")


def _read_env_file_key(var_name: str) -> Optional[str]:
    """从当前 profile 的 .env（其次 Hermes 根 .env）读取变量真值。

    systemd override 里的 ${VAR} 在 manager 未定义该变量时会原样进入进程
    环境（不展开），导致 llm_rewrite 拿到字面假值。这里直接回 .env 文件
    取主 provider 使用的同一把 key。只读、不打印明文。
    """
    try:
        from hermes_constants import get_hermes_home
        candidates = [
            get_hermes_home() / ".env",
            get_hermes_home().parent / ".env",
        ]
    except Exception:
        candidates = []
    for path in candidates:
        try:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, val = line.partition("=")
                if k.strip() == var_name:
                    val = val.strip().strip('"').strip("'")
                    if _valid_key(val):
                        return val
        except Exception as exc:
            logger.debug("flavor_hook: 读取 %s 失败: %s", path, exc)
    return None


def _resolve_api_key() -> Optional[str]:
    """解析 LLM key：环境变量有效 → 直接用；否则回 profile .env 读真值。"""
    env_val = os.environ.get("ANTI_AI_LLM_API_KEY")
    if _valid_key(env_val):
        return env_val
    return _read_env_file_key("MINIMAX_CN_API_KEY")


def _llm_rewrite_sync(text: str, max_chunk_chars: int, api_key: str) -> str:
    """在线程中执行的 LLM 改写。异常向上抛，由调用方兜底。"""
    from anti_ai_flavor.llm_rewrite import llm_rewrite
    return llm_rewrite(
        text,
        api_key=api_key,
        max_chunk_chars=max_chunk_chars,
    )


async def apply_flavor_hook(
    text: Optional[str],
    gateway_config: Optional[Dict[str, Any]] = None,
) -> str:
    """对回复应用 flavor 检测/改写。

    返回可发送文本；任何失败路径都返回原文。
    """
    original = text or ""
    cfg = resolve_flavor_config(gateway_config)

    if not cfg["enabled"]:
        return original
    if not _is_eligible(original, int(cfg["min_chars"])):
        return original

    # 标点规范化（纯规则、0 token、幂等）。在评分/改写前先做，后续链路都基于
    # 规范化文本；任何异常都回退原文，不影响回复。
    try:
        text = normalize_punctuation(original)
    except Exception as exc:
        logger.warning("flavor_hook: 标点规范化失败，继续原文: %s", exc)
        text = original
    if not text:
        return original

    score = _rules_score(text)
    if score is not None and score >= int(cfg["pass_score"]):
        logger.info(
            "flavor_hook: rules 分数 %d ≥ %d，放行（%d chars）",
            score, cfg["pass_score"], len(text),
        )
        return text

    # 文本不达标 → 先跑纯 rules 改写，改写后再评分，达标即发（0 token）
    rules_out = _rules_rewrite(text)
    rules_out = rules_out.strip() if rules_out else ""
    if rules_out and rules_out != text:
        rules_out_score = _rules_score(rules_out)
        if rules_out_score is not None and rules_out_score >= int(cfg["pass_score"]):
            logger.info(
                "flavor_hook: rules 改写后分数 %d ≥ %d，采用（%d → %d chars）",
                rules_out_score, cfg["pass_score"], len(text), len(rules_out),
            )
            return normalize_punctuation(rules_out)
        logger.info(
            "flavor_hook: rules 改写后仍 %s < %d，进入 LLM（%d → %d chars）",
            rules_out_score, cfg["pass_score"], len(text), len(rules_out),
        )
    else:
        logger.info("flavor_hook: rules 改写无实质变化，进入 LLM")

    # rules 改写后仍不达标（或评分器不可用）→ LLM 改写。喂给 LLM 的是 rules 产物，
    # 让它在已清洗的基础上重构；rules 失败则用规范化文本。
    llm_input = rules_out or text
    api_key = _resolve_api_key()
    if not api_key:
        logger.warning(
            "flavor_hook: 未解析到可用 LLM key（env/.env 均无效），发原文",
        )
        return text
    try:
        rewritten = await asyncio.wait_for(
            asyncio.to_thread(
                _llm_rewrite_sync,
                llm_input,
                int(cfg["llm_max_chunk_chars"]),
                api_key,
            ),
            timeout=float(cfg["llm_timeout"]),
        )
    except asyncio.TimeoutError:
        logger.warning(
            "flavor_hook: LLM 改写超时（%ss），发原文", cfg["llm_timeout"],
        )
        return text
    except Exception as exc:
        logger.warning("flavor_hook: LLM 改写失败，发原文: %s", exc)
        return text

    rewritten = (rewritten or "").strip()
    if not rewritten:
        logger.warning("flavor_hook: 改写结果为空，发原文")
        return text

    # 受保护内容校验：原文中的 URL/邮箱/版本号/千分位/时间必须逐字保留。
    # LLM 自由发挥可能把 v1.2.3 读成 v14、给 URL 插空格——一旦关键 token 被
    # 破坏或丢失，这次改写不可信，回退规范化原文。
    if not protected_tokens_preserved(llm_input, rewritten):
        logger.warning(
            "flavor_hook: LLM 改写破坏了关键内容（URL/版本/数字），发原文",
        )
        return text

    # 判定改写结果是否可信。不能用“必须保留原文一半长度”的固定比例：
    # 输入若全是空话，LLM 大幅压缩是正确行为。改为：
    #   1) 结果再评分达标 → 直接采用（长度无关）
    #   2) 结果极短（< min_keep_chars 或不到原文 30%）→ 疑似截断，发原文
    #   3) 长度合理 → 采用，避免因评分器保守而拒绝有效改写
    new_score = _rules_score(rewritten)
    if new_score is not None and new_score >= int(cfg["pass_score"]):
        logger.info(
            "flavor_hook: LLM 改写后分数 %d ≥ %d，采用（%d → %d chars）",
            new_score, cfg["pass_score"], len(text), len(rewritten),
        )
        return normalize_punctuation(rewritten)

    too_short = (
        len(rewritten) < int(cfg["min_keep_chars"])
        or len(rewritten) < len(text) * 0.3
    )
    if too_short:
        logger.warning(
            "flavor_hook: 改写结果异常过短（%d → %d chars，score=%s），发原文",
            len(text), len(rewritten), new_score,
        )
        return text

    logger.info(
        "flavor_hook: 已 LLM 改写（原文 rules=%s → 新 rules=%s，%d → %d chars）",
        score, new_score, len(text), len(rewritten),
    )
    return normalize_punctuation(rewritten)
