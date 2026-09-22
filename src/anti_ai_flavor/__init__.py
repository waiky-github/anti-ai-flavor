"""
anti-ai-flavor — 中文去 AI 味工具

核心 API：
  rewrite_text(text, scene="default") -> str
  detect_all(text) -> dict
  auto_detect_scene(file_path, content="") -> str
  rewrite_file_with_auto_scene(file_path, output_path=None) -> dict
  detect_density(text, threshold_tier2=3, threshold_tier3=1) -> dict
  check_paragraph_density(paragraphs, threshold_tier2=2, threshold_tier3=1) -> list[dict]
"""

from .core import (
    rewrite_text,
    detect_all,
    auto_detect_scene,
    rewrite_file_with_auto_scene,
    detect_density,
    check_paragraph_density,
)
from .scoring import score_text, rewrite_with_report, ScoreResult
from .watermark import detect_watermark
from .llm_rewrite import llm_rewrite

__version__ = "0.1.0"
__all__ = [
    "rewrite_text",
    "detect_all",
    "auto_detect_scene",
    "rewrite_file_with_auto_scene",
    "detect_density",
    "check_paragraph_density",
    "score_text",
    "rewrite_with_report",
    "ScoreResult",
    "detect_watermark",
    "llm_rewrite",
]
