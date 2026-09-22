#!/usr/bin/env python3
"""Golden test set runner for anti-ai-flavor skill.

Usage:
    python test_golden_set.py
    python test_golden_set.py --mode pattern
    python test_golden_set.py --mode legacy
"""

import argparse
import json
import sys

from anti_ai_flavor import rewrite_text as rewrite, detect_all as detect


def load_golden_set():
    """Load golden test cases from JSON file."""
    import importlib.resources as pkg_resources
    data = pkg_resources.files("anti_ai_flavor").joinpath("golden_set.json").read_text(encoding="utf-8")
    return json.loads(data)


def run_tests(mode="all"):
    """Run golden test set and report results."""
    test_cases = load_golden_set()
    results = {"passed": 0, "failed": 0, "details": []}

    for tc in test_cases:
        if mode == "all" or mode == "pattern":
            result = rewrite(tc["input"])
            expected = tc.get("expected_pattern_mode", tc["expected_legacy_mode"])
            passed = result.strip() == expected.strip()
            results["details"].append({
                "id": tc["id"],
                "mode": "pattern",
                "input": tc["input"],
                "expected": expected,
                "actual": result,
                "passed": passed,
                "note": tc.get("note", "")
            })
            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

        if mode == "all" or mode == "legacy":
            # Legacy mode is the same as pattern mode in current implementation
            # but kept separate for backward compatibility testing
            result = rewrite(tc["input"])
            expected = tc["expected_legacy_mode"]
            passed = result.strip() == expected.strip()
            results["details"].append({
                "id": tc["id"],
                "mode": "legacy",
                "input": tc["input"],
                "expected": expected,
                "actual": result,
                "passed": passed,
                "note": tc.get("note", "")
            })
            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

    return results


def print_results(results):
    """Print test results in a readable format."""
    total = results["passed"] + results["failed"]
    print(f"\n[Golden Test Results] {results['passed']}/{total} passed\n")

    for detail in results["details"]:
        status = "✅" if detail["passed"] else "❌"
        print(f"{status} {detail['id']} [{detail['mode']}]")
        if not detail["passed"]:
            print(f"  Input:    {detail['input']}")
            print(f"  Expected: {detail['expected']}")
            print(f"  Actual:   {detail['actual']}")
            if detail["note"]:
                print(f"  Note:     {detail['note']}")
        print()

    if results["failed"] > 0:
        print(f"❌ {results['failed']} test(s) failed")
        return 1
    else:
        print(f"✅ All {results['passed']} test(s) passed")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Run golden test set for anti-ai-flavor")
    parser.add_argument("--mode", choices=["all", "pattern", "legacy"], default="all",
                        help="Test mode: all (default), pattern, or legacy")
    args = parser.parse_args()

    results = run_tests(args.mode)
    exit_code = print_results(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
