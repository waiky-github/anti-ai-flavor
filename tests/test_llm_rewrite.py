#!/usr/bin/env python3
"""tests/test_llm_rewrite.py — llm_rewrite 单测（mock OpenAI）"""

import os
from unittest.mock import MagicMock, patch

import pytest

from anti_ai_flavor.llm_rewrite import llm_rewrite


def test_llm_rewrite_success():
    """正常返回路径：mock openai.OpenAI 返回改写文本"""
    mock_openai = MagicMock()
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="改写后的文本。"))]
    )
    mock_openai.OpenAI.return_value = mock_client

    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            result = llm_rewrite(
                "这个功能展示了我们强大的技术实力。",
                api_key="sk-test",
            )
    assert result == "改写后的文本。"


def test_llm_rewrite_empty_key():
    """空 key 路径：应 raise ValueError"""
    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with pytest.raises(ValueError, match="LLM rewrite 需要"):
            llm_rewrite("test text")


def test_llm_rewrite_network_error():
    """网络异常路径：应 raise RuntimeError"""
    mock_openai = MagicMock()
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("timeout")
    mock_openai.OpenAI.return_value = mock_client

    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            with pytest.raises(RuntimeError, match="LLM rewrite 调用失败"):
                llm_rewrite("test text", api_key="sk-test")


def test_llm_rewrite_strips_thinking_block():
    """minimax-M3 默认开 thinking，content 混入 <think>...</think> 块必须剥离"""
    mock_openai = MagicMock()
    mock_client = MagicMock()
    # 模拟 minimax-M3 返回：thinking 块 + 真实改写结果
    mock_content = (
        "<think>用户希望我去AI味儿。我需要保留原意但口语化。\n\n"
        "改写后：咱们的产品功能挺扎实，使用体验也不错，关键它能给客户带来真正价值。</think>\n"
        "咱们的产品功能挺扎实，使用体验也不错，关键它能给客户带来真正价值。"
    )
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=mock_content))]
    )
    mock_openai.OpenAI.return_value = mock_client

    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            result = llm_rewrite(
                "我们的产品功能强大，能够为客户创造价值。",
                api_key="sk-test",
            )
    # 剥离 thinking 后只剩真实改写
    assert "<think>" not in result
    assert "</think>" not in result
    assert result == "咱们的产品功能挺扎实，使用体验也不错，关键它能给客户带来真正价值。"


def test_llm_rewrite_thinking_only_raises():
    """边界情况：剥离 thinking 后为空 → raise RuntimeError"""
    mock_openai = MagicMock()
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="<think>全是思考过程</think>"))]
    )
    mock_openai.OpenAI.return_value = mock_client

    with patch.dict(os.environ, {"ANTI_AI_LLM_API_KEY": ""}, clear=False):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            with pytest.raises(RuntimeError, match="剥离 thinking 块后为空"):
                llm_rewrite("test", api_key="sk-test")
