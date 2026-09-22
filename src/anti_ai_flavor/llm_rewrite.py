#!/usr/bin/env python3
"""
anti_ai_flavor/llm_rewrite.py — 可选 LLM rewrite 插件

设计：
- 独立函数，不侵入 core.py 的 rewrite_text() 管线
- 默认关闭，需显式传入 api_key / base_url / model 才启用
- prompt 约束：只改结构/节奏，不发明事实，不删关键数字
- 失败时 raise 异常，由调用方处理 fallback
"""

from __future__ import annotations

import os
from typing import Optional

from .core import rewrite_text


def llm_rewrite(
    text: str,
    *,
    api_key: Optional[str] = None,
    base_url: str = "https://open.bigmodel.cn/api/paas/v4",
    model: str = "glm-4-flash",
    scene: str = "default",
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """
    使用 LLM 对文本做结构层面的人类化改写。

    参数：
      text：待改写文本
      api_key：LLM API Key；默认读环境变量 ANTI_AI_LLM_API_KEY
      base_url：LLM base URL，默认智谱
      model：模型名，默认 glm-4-flash
      scene：场景，透传给 rewrite_text() 先做 pattern 预清洗，再做 LLM 后处理
      temperature / max_tokens：控制改写自由度

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

    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "llm_rewrite 需要 openai 包，请先 `pip install openai`"
        ) from e

    prompt = (
        "你是一个中文文本人类化专家。请对以下文本做轻微改写，目标是降低 AI 生成痕迹，"
        "同时严格保留原意、事实、数字和专有名词。\n\n"
        "约束：\n"
        "1. 只改句式结构、用词选择、语序节奏，不改变含义\n"
        "2. 不删除任何数字、日期、金额、人名、地名\n"
        "3. 不添加原文没有的新信息\n"
        "4. 去掉剩余套话（如「值得注意的是」「综上所述」「不仅...而且」等）\n"
        "5. 保持自然口语感，避免过度正式\n"
        "6. 只输出改写后文本，不要解释\n\n"
        f"---\n{pre_cleaned}\n---"
    )

    client = OpenAI(api_key=resolved_key, base_url=base_url)

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        raise RuntimeError(f"LLM rewrite 调用失败: {e}") from e

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("LLM rewrite 返回空内容")

    return content.strip()
