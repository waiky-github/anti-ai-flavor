"""
Flavor hook — gateway 回复发出前自动检测并清洗「AI 味儿」。

在普通消息路径（非 slash 命令、非 streaming）handler 返回文本后调用：
  1. 只处理纯中文文本（无 MEDIA:/图片/附件标记），长度达阈值；
  2. rules-only score_text 毫秒检测，分数达标直接放行，不烧 token；
  3. 不达标 → 线程池跑 llm_rewrite（MiniMax-M3 默认），带超时；
  4. 任何异常 / 超时 / 改写结果异常 → 原样返回，绝不能因为本 hook 吞掉回复。

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
import re
from typing import Any, Dict, Optional

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


def _llm_rewrite_sync(text: str, max_chunk_chars: int) -> str:
    """在线程中执行的 LLM 改写。异常向上抛，由调用方兜底。"""
    from anti_ai_flavor.llm_rewrite import llm_rewrite
    return llm_rewrite(
        text,
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

    score = _rules_score(original)
    if score is not None and score >= int(cfg["pass_score"]):
        logger.info(
            "flavor_hook: rules 分数 %d ≥ %d，放行（%d chars）",
            score, cfg["pass_score"], len(original),
        )
        return original

    # 分数不达标（或评分器不可用时按不达标处理）→ LLM 改写
    try:
        rewritten = await asyncio.wait_for(
            asyncio.to_thread(
                _llm_rewrite_sync,
                original,
                int(cfg["llm_max_chunk_chars"]),
            ),
            timeout=float(cfg["llm_timeout"]),
        )
    except asyncio.TimeoutError:
        logger.warning(
            "flavor_hook: LLM 改写超时（%ss），发原文", cfg["llm_timeout"],
        )
        return original
    except Exception as exc:
        logger.warning("flavor_hook: LLM 改写失败，发原文: %s", exc)
        return original

    rewritten = (rewritten or "").strip()
    # 改写结果为空或长度异常缩水（不到原文一半）→ 不信任，发原文
    if not rewritten or len(rewritten) < len(original) * 0.5:
        logger.warning(
            "flavor_hook: 改写结果异常（%d → %d chars），发原文",
            len(original), len(rewritten),
        )
        return original

    logger.info(
        "flavor_hook: 已改写（rules=%s, %d → %d chars）",
        score, len(original), len(rewritten),
    )
    return rewritten
