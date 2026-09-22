#!/usr/bin/env python3
"""tests/test_llm_detector.py — llm_detector 单测"""

import pytest

from anti_ai_flavor.llm_detector import (
    DetectionResult,
    MockLLMDetector,
    create_detector,
)


def test_mock_detector_disabled():
    """enabled=False 时返回空列表"""
    detector = MockLLMDetector(enabled=False)
    assert detector.detect("值得注意的是，这个方案提升了效率。") == []


def test_mock_detector_enabled():
    """enabled=True 时能检出 AI 味"""
    detector = MockLLMDetector(enabled=True)
    results = detector.detect("值得注意的是，这个方案提升了效率。")
    assert len(results) >= 1
    assert any(r.pattern_id == "P08" for r in results)


def test_create_detector_mock():
    """create_detector provider=mock 返回 MockLLMDetector"""
    detector = create_detector(enabled=True, provider="mock")
    assert isinstance(detector, MockLLMDetector)
    assert detector.enabled is True


def test_create_detector_unknown():
    """未知 provider 应 raise ValueError"""
    with pytest.raises(ValueError, match="Unknown provider"):
        create_detector(provider="unknown")
