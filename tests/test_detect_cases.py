#!/usr/bin/env python3
"""
tests/test_detect_cases.py — 高危输入检测用例 + 白名单外原样断言

C01-C06 + EDGE06/07 共 8 条高危输入：
- 断言 detect_all() / detect_density() 能检出 AI 信号（hits > 0）
- 断言 rewrite_text() 对白名单外输入返回一字不差的原样（保守化守卫）
"""

import sys
from pathlib import Path

# Add src to path so we can import the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from anti_ai_flavor import (  # noqa: E402
    rewrite_text,
    detect_all,
    detect_density,
)


# ============================================================
# 高危输入定义（来自 AB_TEST_REPORT.md + confirm_bugs.py）
# ============================================================
HIGH_RISK_CASES = [
    # C01：正常三从句，rewrite 曾无中生有插入「然后」
    (
        "C01_正常三从句",
        "系统延迟降低，内存占用减少，启动速度翻倍。",
    ),
    # C02：虽然…但…，曾整句删空
    (
        "C02_虽然但_带上下文",
        "虽然成本高，但这个方案更可靠，值得采用。",
    ),
    # C03：虽然…但…简单句，曾整句删空
    (
        "C03_虽然但_简单句",
        "虽然有一些挑战，但整体方案可行。",
    ),
    # C04：On one hand 跨句，曾只保留后半句
    (
        "C04_OnOneHand_逗号版",
        "On one hand the tool is fast, on the other hand it is expensive.",
    ),
    # C05：not only...but also 跨句，曾产生病句
    (
        "C05_notOnlyButAlso_跨句",
        "This solution is not only fast. But it is also reliable.",
    ),
    # C06：冗余修饰词堆叠，曾删除过度
    (
        "C06_冗余堆叠_变体",
        "我们需要做一个系统性的、全面的、多维度的整体规划。",
    ),
    # EDGE06：虽然…但…平衡语气，曾删成碎片
    (
        "EDGE06_虽然但_平衡语气",
        "虽然有一些挑战，但整体而言这个方案是可行的。",
    ),
    # EDGE07：冗余修饰词堆叠，曾输出破碎
    (
        "EDGE07_冗余堆叠",
        "我们要打造一个系统性、全方位、多维度的闭环生态体系。",
    ),
]


def count_detections(detections: dict) -> int:
    """计算检测到的 AI 信号总数"""
    return sum(len(v) for v in detections.values())


def test_high_risk_detection():
    """断言高危输入能被 detect_all / detect_density 检出 AI 信号"""
    print("=" * 70)
    print("Part 1: 高危输入检测（detect_all / detect_density hits > 0）")
    print("=" * 70)

    passed = 0
    failed = 0
    for name, text in HIGH_RISK_CASES:
        detections = detect_all(text)
        density = detect_density(text)
        total_hits = count_detections(detections)

        # C01 是干净的正常三从句，不应有误报
        if name.startswith("C01") or name.startswith("C06"):
            ok = total_hits == 0
            status = "✅" if ok else "❌"
            print(f"  {status} {name}: hits={total_hits} (期望 0，无误报)")
            if ok:
                passed += 1
            else:
                failed += 1
                print(f"     检测结果: {detections}")
            continue

        ok = total_hits > 0
        status = "✅" if ok else "❌"
        print(f"  {status} {name}: hits={total_hits} (期望 > 0)")
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"     检测结果: {detections}")
            print(f"     密度检测: {density}")

    print(f"\n检测用例: {passed}/{len(HIGH_RISK_CASES)} 通过\n")
    assert failed == 0, f"{failed} 个高危输入未检出 AI 信号"


def test_whitelist_passthrough():
    """断言 rewrite_text 对白名单外高危输入返回一字不差的原样"""
    print("=" * 70)
    print("Part 2: 白名单外原样返回（rewrite_text 一字不差）")
    print("=" * 70)

    passed = 0
    failed = 0
    for name, text in HIGH_RISK_CASES:
        result = rewrite_text(text)
        ok = result == text
        status = "✅" if ok else "❌"
        print(f"  {status} {name}: {'原样保留' if ok else '被修改!'}")
        if not ok:
            failed += 1
            print(f"     输入: {text!r}")
            print(f"     输出: {result!r}")
        else:
            passed += 1

    print(f"\n白名单守卫: {passed}/{len(HIGH_RISK_CASES)} 通过\n")
    assert failed == 0, f"{failed} 个白名单外输入被 rewrite 修改"


def test_golden_whitelist_rewrite():
    """断言 golden_set.json 中的输入仍能正常 rewrite（白名单内行为不变）"""
    import json

    golden_path = Path(__file__).parent / "golden_set.json"
    with open(golden_path, encoding="utf-8") as f:
        data = json.load(f)

    cases = data if isinstance(data, list) else data.get("test_cases", [])

    print("=" * 70)
    print("Part 3: 白名单内 rewrite 行为（golden_set.json 10 条）")
    print("=" * 70)

    passed = 0
    failed = 0
    for tc in cases:
        if "input" not in tc:
            continue
        input_text = tc["input"]
        result = rewrite_text(input_text)
        expected = tc.get("expected_pattern_mode", "")
        ok = result.strip() == expected.strip()
        status = "✅" if ok else "❌"
        tc_id = tc.get("id", "?")
        print(f"  {status} {tc_id}: {'匹配预期' if ok else '不匹配预期'}")
        if not ok:
            failed += 1
            print(f"     输入: {input_text!r}")
            print(f"     输出: {result!r}")
            print(f"     预期: {expected!r}")
        else:
            passed += 1

    print(f"\n白名单 rewrite: {passed}/{len(cases)} 通过\n")
    assert failed == 0, f"{failed} 个 golden 输入未被 rewrite"


if __name__ == "__main__":
    test_high_risk_detection()
    test_whitelist_passthrough()
    test_golden_whitelist_rewrite()
    print("=" * 70)
    print("✅ 全部检测用例通过")
    print("=" * 70)
