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
