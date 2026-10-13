"""
Flavor hook — gateway 回复发出前自动检测并清洗「AI 味儿」。

在普通消息路径（非 slash 命令、非 streaming）handler 返回文本后调用：
  1. 只处理纯中文文本（无 MEDIA:/图片/附件标记），长度达阈值；
  2. rules-only score_text 毫秒检测，分数达标直接放行，不烧 token；
  3. 不达标 → 先跑纯 rules rewrite_text，改写后再评分，达标即发（0 token）；
  4. rules 改写后仍不达标（或没实质变化）→ LLM 改写，带超时。模型通道二选一：
     a) 宿主注入 transport（Hermes gateway）：走 agent.auxiliary_client，协议无关、
        自带主 provider→fallback 链，读 auxiliary.flavor.{provider,model} 覆盖，
        缺省 auto=用当前主模型；本模块不自读 key。
     b) 独立 / CLI 未注入：OpenAI 直连（默认 MiniMax-M3，读 ANTI_AI_LLM_* 或
        profile .env 的 MINIMAX_CN_API_KEY），在线程池执行。
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
from anti_ai_flavor.phrase_rewrite import phrase_rewrite

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
    # 发送模式：
    #   "sync"      发送前同步跑完 rules+LLM（默认；CLI/独立使用的旧行为，会阻塞
    #               回复，最长 llm_timeout）
    #   "async_edit" 先立即发原文（毫秒判定），再后台 LLM 改写并用平台 edit_message
    #               静默就地替换；平台不支持编辑或改写不可信时保留已发原文。
    #               Hermes gateway 部署时在 config.yaml 显式开启。
    "mode": "sync",
    # 技术内容守卫：含围栏/行内代码块或 URL 的回复不进 LLM（LLM 对版本号/命令/
    # 链接容易自由发挥，且这类回复用户对延迟敏感）。只在 async_edit 模式于后台
    # 判定；sync 模式仍走原逻辑（由 protected_tokens 校验兜底）。
    "skip_code_for_llm": True,
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


def _contains_structured_content(text: str) -> bool:
    """技术内容守卫：回复是否含代码块 / 行内代码 / URL / 邮箱。

    这类回复（命令、版本号、链接、代码）进 LLM 既慢又容易被自由发挥破坏关键
    token，且用户对其延迟敏感。命中即不进 LLM（标点规范化/短语改写仍安全）。
    复用 punctuation 里的受保护结构正则，避免两处词表漂移。
    """
    try:
        from anti_ai_flavor.punctuation import _PROTECT_RES
        return any(rx.search(text) for rx in _PROTECT_RES)
    except Exception:
        # 拿不到正则时保守判定：只认围栏代码块
        return "```" in (text or "")


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


# ── 可注入的宿主模型传输层 ─────────────────────────────────────────────
# 部署在 Hermes gateway 时，由 wrapper（gateway/flavor_hook.py）在导入期注册一个
# async transport，内部走 agent.auxiliary_client（协议无关、自带主 provider→fallback
# 链、读 auxiliary.flavor.{provider,model} 覆盖）。注册后 hook 不再自读 key、不自建
# OpenAI 连接；未注册（CLI / 独立使用）时回退下面的直连路径，行为与旧版一致。
_LLM_TRANSPORT = None


def register_llm_transport(transport) -> None:
    """注册宿主模型传输层。transport(messages: list[dict]) -> str | awaitable[str]。"""
    global _LLM_TRANSPORT
    _LLM_TRANSPORT = transport


def get_registered_llm_transport():
    """返回当前注册的 transport（未注册为 None）。主要供测试与诊断使用。"""
    return _LLM_TRANSPORT


async def _llm_rewrite_via_transport(
    text: str,
    max_chunk_chars: int,
    transport,
    max_attempts: int = 3,
) -> str:
    """通过注入的宿主 transport 异步改写。

    与直连路径一致：模型偶发只输出 thinking 不给正文（``剥离 thinking 块后为空``）
    属瞬时失败，自动重试至多 max_attempts 次；其他异常立即上抛，由外层兜底发原文。
    """
    from anti_ai_flavor.llm_rewrite import llm_rewrite_async

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await llm_rewrite_async(
                text,
                transport=transport,
                max_chunk_chars=max_chunk_chars,
            )
        except RuntimeError as exc:
            if "剥离 thinking 块后为空" not in str(exc):
                raise
            last_exc = exc
            logger.info(
                "flavor_hook: LLM 第 %d/%d 次只输出 thinking 未给正文，重试",
                attempt, max_attempts,
            )
    assert last_exc is not None
    raise last_exc


def _llm_rewrite_sync(
    text: str,
    max_chunk_chars: int,
    api_key: str,
    max_attempts: int = 3,
) -> str:
    """在线程中执行的 LLM 改写。异常向上抛，由调用方兜底。

    模型偶发只输出 thinking、不产出正文（``剥离 thinking 块后为空``），属瞬时
    失败——此处对该特定错误自动重试至多 ``max_attempts`` 次，提升成功率；其他
    异常（鉴权/网络/超时等）不重试，立即上抛。
    """
    from anti_ai_flavor.llm_rewrite import llm_rewrite
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return llm_rewrite(
                text,
                api_key=api_key,
                max_chunk_chars=max_chunk_chars,
            )
        except RuntimeError as exc:
            if "剥离 thinking 块后为空" not in str(exc):
                raise
            last_exc = exc
            logger.info(
                "flavor_hook: LLM 第 %d/%d 次只输出 thinking 未给正文，重试",
                attempt, max_attempts,
            )
    assert last_exc is not None
    raise last_exc


async def _run_full_pipeline(original: str, cfg: Dict[str, Any]) -> str:
    """完整 rules→(LLM) 改写链路。任何失败路径返回原文。

    调用方需已通过 enabled / eligible 判定。sync 模式与 async_edit 后台共用。
    """
    text = original
    # 标点规范化（纯规则、0 token、幂等）。在评分/改写前先做，后续链路都基于
    # 规范化文本；任何异常都回退原文，不影响回复。
    try:
        text = normalize_punctuation(original)
    except Exception as exc:
        logger.warning("flavor_hook: 标点规范化失败，继续原文: %s", exc)
        text = original
    if not text:
        return original

    # —— 关键顺序：先短语改写，再评分 ——
    # gating 评分器与短语表是两套词表：评分器只认识「生态/闭环/全方位…」等
    # 强信号，而「拉齐颗粒度/组合拳/品效合一」等会议黑话它不扣分（会给 100）。
    # 若「先评分放行」，满是后者的回复会在改写前被直接放行。因此先跑短语改写
    # （只替换命中搭配、无命中原样返回），再对产物评分。
    try:
        rules_out = phrase_rewrite(text)
    except Exception as exc:
        logger.warning("flavor_hook: 短语改写失败，按原文继续: %s", exc)
        rules_out = text
    rules_out = rules_out.strip() if rules_out else ""

    # 无命中 / 命中后破坏了受保护内容 → 回退原文，只按评分器判定。
    if not rules_out or rules_out == text:
        rules_out = ""
    elif not protected_tokens_preserved(text, rules_out):
        logger.info("flavor_hook: 短语改写破坏了关键内容，忽略改写")
        rules_out = ""

    # 需要评分的文本：有有效改写则评产物，否则评规范化原文。
    candidate = rules_out or text
    score = _rules_score(candidate)
    if score is not None and score >= int(cfg["pass_score"]):
        if rules_out:
            logger.info(
                "flavor_hook: 短语改写后分数 %d ≥ %d，采用（%d → %d chars）",
                score, cfg["pass_score"], len(text), len(rules_out),
            )
        else:
            logger.info(
                "flavor_hook: rules 分数 %d ≥ %d，放行（%d chars）",
                score, cfg["pass_score"], len(text),
            )
        return normalize_punctuation(candidate)

    # 短语改写无命中（或被忽略）且评分器也不认识 → 干净但低分的文本直接放行，
    # 不必为评分器盲区浪费一次 LLM；只有确实存在可识别 AI 味时才继续。
    if not rules_out and (score is None):
        return text

    if rules_out:
        logger.info(
            "flavor_hook: 短语改写后仍 %s < %d，进入 LLM（%d → %d chars）",
            score, cfg["pass_score"], len(text), len(rules_out),
        )
    else:
        logger.info(
            "flavor_hook: rules 分数 %s < %d，进入 LLM", score, cfg["pass_score"],
        )

    # 短语改写后仍不达标（或无命中）→ LLM 改写。喂给 LLM 的是候选文本。
    llm_input = candidate
    transport = _LLM_TRANSPORT
    try:
        if transport is not None:
            # 宿主注入通道（Hermes auxiliary_client）：协议无关、自带 provider
            # fallback、读 auxiliary.flavor 覆盖；无需本模块自读 key。
            rewritten = await asyncio.wait_for(
                _llm_rewrite_via_transport(
                    llm_input, int(cfg["llm_max_chunk_chars"]), transport
                ),
                timeout=float(cfg["llm_timeout"]),
            )
        else:
            # 独立 / CLI 回退：OpenAI 直连（默认 MiniMax-M3）。
            api_key = _resolve_api_key()
            if not api_key:
                logger.warning(
                    "flavor_hook: 未解析到可用 LLM key（env/.env 均无效），发原文",
                )
                return text
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


async def prepare_flavor_send(
    text: Optional[str],
    gateway_config: Optional[Dict[str, Any]] = None,
) -> tuple:
    """发送前同步阶段（必须毫秒返回，绝不阻塞回复）。

    返回 ``(send_text, pending_text)``：
      * 不处理 / sync 模式 → ``(可直接发送的文本, None)``
      * async_edit 模式   → ``(原文, 原文)``：立即把原文发出，调用方在发送成功
        拿到 message_id 后，用 pending_text 调 :func:`rewrite_post_send` 后台改写，
        再用平台 edit_message 就地替换。

    async_edit 模式下本函数**不做任何 LLM/规则改写**，只做 enabled/eligible 判定，
    因此已发文本与最终文本之间不会出现"先短语改写、后又 LLM 重写"的二次跳变；
    所有清洗都在后台一次性完成，失败则保留已发原文。
    """
    original = text or ""
    cfg = resolve_flavor_config(gateway_config)

    if not cfg["enabled"] or not original:
        return original, None
    if not _is_eligible(original, int(cfg["min_chars"])):
        return original, None

    if str(cfg.get("mode", "sync")) == "async_edit":
        # 立即发原文；改写交给后台（含技术守卫）。
        return original, original

    # sync 旧行为：发送前跑完整个 rules+LLM 链路（会阻塞，最长 llm_timeout）。
    return await _run_full_pipeline(original, cfg), None


async def rewrite_post_send(
    text: Optional[str],
    gateway_config: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """发送后后台改写（async_edit 模式）。

    对已发出的原文做完整 rules→LLM 清洗。返回应替换成的新文本；无需替换（文本
    干净、改写不可信、命中技术守卫、任何失败）时返回 ``None``，调用方保留已发
    原文、绝不重复编辑。
    """
    original = text or ""
    cfg = resolve_flavor_config(gateway_config)

    if not cfg["enabled"] or not original:
        return None
    if not _is_eligible(original, int(cfg["min_chars"])):
        return None

    # 技术内容守卫：代码块/行内代码/URL/邮箱不进 LLM。这类回复 LLM 易破坏版本号、
    # 命令、链接（曾导致 91s 白等后回退原文），且用户对其延迟/准确性敏感。
    if cfg.get("skip_code_for_llm", True) and _contains_structured_content(original):
        logger.info(
            "flavor_hook: 含代码/链接等技术内容，跳过后台 LLM 改写（%d chars）",
            len(original),
        )
        return None

    out = await _run_full_pipeline(original, cfg)
    out = (out or "").strip()
    if not out or out == original:
        return None
    return out


async def apply_flavor_hook(
    text: Optional[str],
    gateway_config: Optional[Dict[str, Any]] = None,
) -> str:
    """对回复应用 flavor 检测/改写（兼容入口）。

    - mode=sync（旧行为）：发送前跑完 rules+LLM，返回可发送文本，可能阻塞。
    - mode=async_edit：等价于只取 :func:`prepare_flavor_send` 的即时发送文本
      （即原文）；真正的改写应由调用方在发送成功后走 :func:`rewrite_post_send`。

    任何失败路径都返回原文。
    """
    send_text, _pending = await prepare_flavor_send(text, gateway_config)
    return send_text
