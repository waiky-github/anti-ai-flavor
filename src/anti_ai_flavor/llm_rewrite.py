#!/usr/bin/env python3
"""
anti_ai_flavor/llm_rewrite.py — 可选 LLM rewrite 插件

设计：
- 独立函数，不侵入 core.py 的 rewrite_text() 管线
- 默认关闭，需显式传入 api_key / base_url / model 才启用
- prompt 约束：只改结构/节奏，可补项目落地叙事，不发明事实，不删关键数字
- 失败时 raise 异常，由调用方处理 fallback
- 长文本自动按 1700 字符切段调用后合并（避免 thinking 占满 max_tokens）
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

from .core import rewrite_text


# 默认 LLM 端点：minimax 国内 OpenAI 兼容（MiniMax-M3，1M 上下文，MSA 架构）
# 实际以 ANTI_AI_LLM_BASE_URL env 为准（minimaxi.com 是新版本域名）
DEFAULT_BASE_URL = "https://api.minimaxi.com/v1"
DEFAULT_MODEL = "MiniMax-M3"


# v0.2.9.3 升级目标：从"AI 在做句子重构" → "真人工程师在写项目落地叙事"
# 关键变化：放行"基于原文事实的工程实施细节补全"，强调拆句+具体动词
# （deepseek v9 = 2481 字 vs 我们 v8-rules+llm = 1697 字 → 真人补了 800 字项目落地细节）
SYSTEM_PROMPT = """你是中文写作专家，正在以「真人资深工程师」口吻重写用户文本。

【目标】读起来像 10 年经验的工程师亲手写的简历/技术文，不是 AI 生成的。

【关键原则】
1. 拆句：把 50+ 字的长句拆成 2-3 个短句，每句一个核心信息
2. 改动词：用具体动作词替换抽象套话
   打造/构建 → 搭了/做了
   赋能/支撑 → 用来/支撑
   提升/优化 → 提速 X%（带数字）
   全方位/多维度 → 删掉或换成具体场景
3. 补项目落地叙事：每个成果后面加 1 句「面向 XX 场景/解决 XX 问题，完成 XX 实施」
   例：「在 GPU 上部署大模型」→「基于 4×A100 80GB，采用 vLLM 部署 Qwen3.6-27B，配置 FP8 量化、TP=4 张量并行及模型原生 MTP 推测解码；面向多并发推理场景完成推理引擎选型、量化调优与服务上线」
4. 删冗余：原文重复信息保留一处即可

【严格不改】
所有数字（百分比/容量/版本号/人数）
所有日期
所有技术栈名称（vLLM/RAG/FastAPI/Ollama/Python/...）
所有专有名词（公司/产品/人名）
所有段落标题和整体段落顺序

【绝对不能写】
不仅...而且 / 更重要的是 / 值得注意的是 / 综上所述 / 总而言之
全方位 / 多维度 / 多层次 / 可持续 / 高质量发展
打造 / 构建 / 赋能 / 协同 / 优化 / 升级 / 实现 / 推动 / 助力
众所周知 / 随着...发展 / 在当今时代 / 不可否认

【语调】
核心描述用书面（基于/采用/配置/完成/搭建）
动词/结果用口语（搭了/做出来/支撑/跑起来/打通）
不要全篇口语化（不像工程师）
不要全篇书面化（不像真人）

【项目细节补充规则】
如果用户提供了 project_context（通用细节）或 project_sections（按段落标题精细控制）：
- 只补与原文内容相关的细节，不扩展原文没有的功能模块
- 数字/日期/技术栈以原文为准，项目细节只补「叙事性描述」（团队规模/项目周期/业务场景/解决的痛点）
- 按段落提供的细节，只在改写到对应段落时使用；其他段落忽略
- 如果提供的细节与原文矛盾，以原文为准（不发明事实）

只输出改写后文本，不要任何解释/思考过程/格式包装。"""


def _split_long_text(text: str, max_chars: int = 1700) -> List[str]:
    """按段落切分长文本，避免单次 LLM 调用 thinking 占满 max_tokens。

    切分策略：
      - 空行（\\n\\n）是自然段落边界，优先在空行切
      - 单个段落超 max_chars 时，按句号/问号/感叹号切（保留标点）
      - 切完后每段 < max_chars
    """
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for p in paragraphs:
        p_len = len(p)

        # 单段超长 → 按句子再切
        if p_len > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            sentences = re.split(r"(?<=[。！？!?])\s*", p)
            sub: List[str] = []
            sub_len = 0
            for s in sentences:
                if sub_len + len(s) > max_chars and sub:
                    chunks.append("".join(sub))
                    sub = [s]
                    sub_len = len(s)
                else:
                    sub.append(s)
                    sub_len += len(s)
            if sub:
                chunks.append("".join(sub))
            continue

        # 累积超长 → 先 flush
        if current_len + p_len + 2 > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [p]
            current_len = p_len
        else:
            current.append(p)
            current_len += p_len + 2

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _strip_thinking(content: str) -> str:
    """剥离 minimax-M3 thinking 块（<think>...</think>）。"""
    cleaned = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL).strip()
    return cleaned


def _build_user_prompt(
    text: str,
    project_context: Optional[str] = None,
    project_sections: Optional[Dict[str, str]] = None,
) -> str:
    """构造 user 角色 prompt：待改写文本 + 可选项目细节。"""
    parts = [f"---待改写文本---\n{text}\n---"]

    has_context = bool(project_context)
    has_sections = bool(project_sections)
    if has_context or has_sections:
        parts.append("\n【项目细节（可选）】改写时可参考以下细节补充「叙事性描述」：")
        if has_context:
            parts.append(f"\n[通用细节]\n{project_context}")
        if has_sections:
            parts.append("\n[按段落标题]")
            for title, detail in project_sections.items():
                parts.append(f"- 「{title}」: {detail}")

    return "\n".join(parts)


def _llm_call_once(
    text: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
    project_context: Optional[str] = None,
    project_sections: Optional[Dict[str, str]] = None,
) -> str:
    """单段 LLM 调用：构造 prompt → 调 API → 剥 thinking。"""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "llm_rewrite 需要 openai 包，请先 `pip install openai`"
        ) from e

    user_prompt = _build_user_prompt(text, project_context, project_sections)

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        raise RuntimeError(f"LLM rewrite 调用失败: {e}") from e

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("LLM rewrite 返回空内容")

    content_clean = _strip_thinking(content)
    if not content_clean:
        raise RuntimeError("LLM rewrite 剥离 thinking 块后为空")

    return content_clean


def llm_rewrite(
    text: str,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    scene: str = "default",
    temperature: float = 0.3,
    max_tokens: int = 8000,
    timeout: float = 60.0,
    max_chunk_chars: int = 1500,
    project_context: Optional[str] = None,
    project_sections: Optional[Dict[str, str]] = None,
) -> str:
    """
    使用 LLM 对文本做结构层面的人类化改写。

    参数：
      text：待改写文本
      api_key：LLM API Key；默认读环境变量 ANTI_AI_LLM_API_KEY
      base_url：LLM base URL；默认 ANTI_AI_LLM_BASE_URL → minimax 国内（MiniMax-M3）
      model：模型名；默认 ANTI_AI_LLM_MODEL → MiniMax-M3
      scene：场景，透传给 rewrite_text() 先做 pattern 预清洗，再做 LLM 后处理
      temperature / max_tokens：控制改写自由度（默认 max_tokens=8000，给 minimax-M3 thinking 留足额度；实测 thinking 可占 4000+ token）
      max_chunk_chars：长文本切分阈值（默认 1500 字符），避免单段太长导致 thinking 占满 max_tokens
      project_context：自由文本项目细节（团队规模/项目周期/业务场景/解决的痛点），LLM 改写时参考补「叙事性描述」
      project_sections：按段落标题精细控制，dict[段标题, 细节]。仅改写到对应段落时使用，其他段落忽略

    返回：
      改写后的文本

    异常：
      ImportError：未装 openai 依赖
      ValueError：未配置 API key
      RuntimeError：LLM 调用失败
    """
    # 先做 pattern 预清洗，再给 LLM 做后处理，避免 LLM 重复处理规则已覆盖的套话
    pre_cleaned = rewrite_text(text, scene=scene)

    resolved_key = api_key or os.environ.get("ANTI_AI_LLM_API_KEY", "")
    if not resolved_key:
        raise ValueError(
            "LLM rewrite 需要显式传入 api_key 或设置环境变量 ANTI_AI_LLM_API_KEY"
        )

    # base_url / model 优先级：参数 > ANTI_AI_LLM_* env > minimax 默认
    resolved_base_url: str = (
        base_url
        or os.environ.get("ANTI_AI_LLM_BASE_URL")
        or DEFAULT_BASE_URL
    )
    resolved_model: str = (
        model
        or os.environ.get("ANTI_AI_LLM_MODEL")
        or DEFAULT_MODEL
    )

    # 长文本自动分段：避免单段太长，thinking 占满 max_tokens 导致改写被截断
    chunks = _split_long_text(pre_cleaned, max_chars=max_chunk_chars)

    if len(chunks) == 1:
        return _llm_call_once(
            chunks[0],
            api_key=resolved_key,
            base_url=resolved_base_url,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            project_context=project_context,
            project_sections=project_sections,
        )

    # 多段：每段独立调用，最后用空行拼接
    # 项目细节在每段都传（LLM 自己识别是否相关），不做段落级匹配
    rewritten_chunks = []
    for chunk in chunks:
        rewritten_chunks.append(
            _llm_call_once(
                chunk,
                api_key=resolved_key,
                base_url=resolved_base_url,
                model=resolved_model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                project_context=project_context,
                project_sections=project_sections,
            )
        )
    return "\n\n".join(rewritten_chunks)