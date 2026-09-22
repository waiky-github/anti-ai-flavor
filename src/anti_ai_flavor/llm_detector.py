"""
llm_detector.py — LLM-based AI flavor detector (Phase 2)

只读检测，不改写文本。默认关闭，需要显式启用。
零额外依赖，直接用 requests 调 OpenAI / Anthropic HTTP API。
"""

from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from typing import List, Optional

import requests


@dataclass
class DetectionResult:
    pattern_id: str
    pattern_name: str
    confidence: float
    matched_text: str
    suggestion: str


class LLMDetector:
    """LLM 检测器基类（只读，不改写）"""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def detect(self, text: str) -> List[DetectionResult]:
        """检测文本中的 AI 味特征"""
        if not self.enabled:
            return []
        raise NotImplementedError


class _BaseHTTPDetector(LLMDetector):
    """基于 HTTP API 的检测器基类"""

    api_key_env: str = ""
    url: str = ""
    model: str = ""
    provider: str = ""

    def _call_api(self, text: str) -> Optional[str]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            warnings.warn(
                f"{self.provider} API key not found in env {self.api_key_env}, "
                "fallback to empty results"
            )
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = self._build_payload(text)

        try:
            resp = requests.post(
                self.url, headers=headers, json=payload, timeout=30
            )
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            warnings.warn(
                f"{self.provider} API call failed ({exc}), fallback to empty results"
            )
            return None

    def _build_payload(self, text: str) -> dict:
        raise NotImplementedError

    def _parse_response(self, raw: str) -> List[dict]:
        raise NotImplementedError

    def detect(self, text: str) -> List[DetectionResult]:
        if not self.enabled:
            return []
        raw = self._call_api(text)
        if raw is None:
            return []
        items = self._parse_response(raw)
        results = []
        for item in items:
            try:
                results.append(DetectionResult(
                    pattern_id=str(item.get("pattern_id", "")),
                    pattern_name=str(item.get("pattern_name", "")),
                    confidence=float(item.get("confidence", 0.0)),
                    matched_text=str(item.get("matched_text", "")),
                    suggestion=str(item.get("suggestion", "")),
                ))
            except (TypeError, ValueError):
                continue
        return results


class OpenAILLMDetector(_BaseHTTPDetector):
    api_key_env = "OPENAI_API_KEY"
    url = "https://api.openai.com/v1/chat/completions"
    model = "gpt-4o-mini"
    provider = "OpenAI"

    def _build_payload(self, text: str) -> dict:
        # 只做检测，不改原文。要求返回 JSON 数组。
        return {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 AI 味特征检测器。只读，不改写文本。\n"
                        "请检查用户文本中是否存在已知 AI 味特征（套话、对称填充、"
                        "过度总结、强制三并列、被动语态、词表 bias 等）。\n"
                        "每个命中项返回一个 JSON 对象：{\n"
                        '  "pattern_id": "Pxx",\n'
                        '  "pattern_name": "中文名称",\n'
                        '  "confidence": 0.0-1.0,\n'
                        '  "matched_text": "命中原文片段",\n'
                        '  "suggestion": "删除/替换/改写建议"\n'
                        "}\n"
                        "如果没有命中，返回空数组 []。\n"
                        "注意：matched_text 必须直接从原文摘抄，不能 paraphrase。"
                    ),
                },
                {"role": "user", "content": text},
            ],
        }

    def _parse_response(self, raw: str) -> List[dict]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
        content = content.strip()
        if not content:
            return []
        # 兼容模型返回 ``json ``` 包裹的情况
        if content.startswith("```"):
            content = content.strip("`")
            if "\n" in content:
                content = content.split("\n", 1)[1]
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                # 某些模型包一层 {"detections": [...]}
                for key in ("detections", "results", "items"):
                    if key in parsed and isinstance(parsed[key], list):
                        return parsed[key]
                return []
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return []


class AnthropicLLMDetector(_BaseHTTPDetector):
    api_key_env = "ANTHROPIC_API_KEY"
    url = "https://api.anthropic.com/v1/messages"
    model = "claude-3-5-haiku-20241022"
    provider = "Anthropic"

    def _build_payload(self, text: str) -> dict:
        return {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": 0,
            "system": (
                "你是 AI 味特征检测器。只读，不改写文本。\n"
                "请检查用户文本中是否存在已知 AI 味特征（套话、对称填充、"
                "过度总结、强制三并列、被动语态、词表 bias 等）。\n"
                "每个命中项返回一个 JSON 对象：{\n"
                '  "pattern_id": "Pxx",\n'
                '  "pattern_name": "中文名称",\n'
                '  "confidence": 0.0-1.0,\n'
                '  "matched_text": "命中原文片段",\n'
                '  "suggestion": "删除/替换/改写建议"\n'
                "}\n"
                "如果没有命中，返回空数组 []。\n"
                "注意：matched_text 必须直接从原文摘抄，不能 paraphrase。\n"
                "最终输出必须是合法 JSON。"
            ),
            "messages": [
                {"role": "user", "content": text},
            ],
        }

    def _parse_response(self, raw: str) -> List[dict]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        blocks = (((data.get("content") or [{}])[0]).get("text") or "").strip()
        if not blocks:
            return []
        if blocks.startswith("```"):
            blocks = blocks.strip("`")
            if "\n" in blocks:
                blocks = blocks.split("\n", 1)[1]
        try:
            parsed = json.loads(blocks)
            if isinstance(parsed, dict):
                for key in ("detections", "results", "items"):
                    if key in parsed and isinstance(parsed[key], list):
                        return parsed[key]
                return []
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return []


class MockLLMDetector(LLMDetector):
    """Mock 检测器（用于测试）"""

    def detect(self, text: str) -> List[DetectionResult]:
        if not self.enabled:
            return []
        results = []
        if "值得注意的是" in text:
            results.append(DetectionResult(
                pattern_id="P08",
                pattern_name="Meta-commentary",
                confidence=0.9,
                matched_text="值得注意的是",
                suggestion="删除",
            ))
        return results


def create_detector(enabled: bool = False, provider: str = "mock") -> LLMDetector:
    """创建检测器"""
    provider = provider.lower().strip()
    if provider == "mock":
        return MockLLMDetector(enabled=enabled)
    if provider == "openai":
        return OpenAILLMDetector(enabled=enabled)
    if provider == "anthropic":
        return AnthropicLLMDetector(enabled=enabled)
    raise ValueError(f"Unknown provider: {provider}. Supported: mock/openai/anthropic")
