#!/usr/bin/env python3
"""
anti_ai_flavor/cli.py — CLI 入口

用法：
  anti-ai-flavor rewrite [file] [--scene default] [-o output]
  anti-ai-flavor density [file]
  anti-ai-flavor check-docs <docs_dir>
  anti-ai-flavor detect [file] [--provider mock] [--json]
"""

import argparse
import json
import sys
from pathlib import Path

from .core import rewrite_text, detect_density, detect_all
from .llm_detector import create_detector


def main():
    parser = argparse.ArgumentParser(description="Anti-AI-Flavor Rewriter")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # rewrite 子命令
    rewrite_parser = subparsers.add_parser("rewrite", help="重写文本")
    rewrite_parser.add_argument("file", nargs="?", help="输入文件路径（默认 stdin）")
    rewrite_parser.add_argument("--scene", default="default", help="场景 pack")
    rewrite_parser.add_argument("--output", "-o", help="输出文件（默认 stdout）")
    rewrite_parser.add_argument("--diff", action="store_true", help="显示 diff")
    rewrite_parser.add_argument("--strict", action="store_true", help="严格模式：漏掉 Tier 1 词时报错")

    # density 子命令
    density_parser = subparsers.add_parser("density", help="检测密度")
    density_parser.add_argument("file", nargs="?", help="输入文件路径（默认 stdin）")

    # check-docs 子命令
    check_parser = subparsers.add_parser("check-docs", help="检查目录下所有 markdown 文件的密度")
    check_parser.add_argument("docs_dir", help="文档目录路径")

    # detect 子命令（Phase 2: LLM 检测）
    detect_parser = subparsers.add_parser("detect", help="LLM 检测 AI 味特征（只读，不改写）")
    detect_parser.add_argument("file", nargs="?", help="输入文件路径（默认 stdin）")
    detect_parser.add_argument("--provider", default="mock", help="检测器提供商（mock/openai/anthropic）")
    detect_parser.add_argument("--json", action="store_true", help="JSON 输出")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # rewrite 子命令
    if args.command == "rewrite":
        if args.file:
            raw = Path(args.file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()

        result = rewrite_text(raw, scene=args.scene)

        if args.output:
            Path(args.output).write_text(result, encoding="utf-8")
            print(f"已写入: {args.output}", file=sys.stderr)
        else:
            print(result)

    # density 子命令
    elif args.command == "density":
        if args.file:
            raw = Path(args.file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()

        result = detect_density(raw)
        if result["should_rewrite"]:
            print(f"⚠️ 建议重写：{', '.join(result['warnings'])}", file=sys.stderr)
            sys.exit(1)
        else:
            print("✅ 密度正常", file=sys.stderr)
            sys.exit(0)

    # check-docs 子命令
    elif args.command == "check-docs":
        docs_dir = Path(args.docs_dir)
        md_files = list(docs_dir.rglob("*.md"))
        if not md_files:
            print(f"未找到 .md 文件: {docs_dir}", file=sys.stderr)
            sys.exit(1)

        print(f"检查 {len(md_files)} 个文档...", file=sys.stderr)
        issues_found = False
        for f in md_files:
            text = f.read_text(encoding="utf-8")
            result = detect_density(text)
            if result["should_rewrite"]:
                issues_found = True
                print(f"\n⚠️ {f}:", file=sys.stderr)
                for w in result["warnings"]:
                    print(f"  - {w}", file=sys.stderr)
                if result["tier2_words"]:
                    print(f"  Tier 2 词: {', '.join(result['tier2_words'])}", file=sys.stderr)
                if result["tier3_words"]:
                    print(f"  Tier 3 词: {', '.join(result['tier3_words'])}", file=sys.stderr)

        if issues_found:
            print(f"\n❌ {len([f for f in md_files if detect_density(f.read_text(encoding='utf-8'))['should_rewrite']])} 个文档需要重写", file=sys.stderr)
            sys.exit(1)
        else:
            print("\n✅ 所有文档密度正常", file=sys.stderr)
            sys.exit(0)

    # detect 子命令
    elif args.command == "detect":
        if args.file:
            raw = Path(args.file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()

        try:
            detector = create_detector(enabled=True, provider=args.provider)
        except ValueError as e:
            print(f"❌ 检测器错误: {e}", file=sys.stderr)
            sys.exit(1)

        results = detector.detect(raw)

        if args.json:
            output = {
                "text": raw,
                "detections": [
                    {
                        "pattern_id": r.pattern_id,
                        "pattern_name": r.pattern_name,
                        "confidence": r.confidence,
                        "matched_text": r.matched_text,
                        "suggestion": r.suggestion,
                    }
                    for r in results
                ]
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            if not results:
                print("✅ 未检测到 AI 味特征")
            else:
                print(f"⚠️ 检测到 {len(results)} 个 AI 味特征：")
                for r in results:
                    print(f"  [{r.pattern_id}] {r.pattern_name} (置信度: {r.confidence:.0%})")
                    print(f"    匹配: {r.matched_text}")
                    print(f"    建议: {r.suggestion}")

        sys.exit(0 if not results else 2)


if __name__ == "__main__":
    main()
