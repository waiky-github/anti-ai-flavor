#!/usr/bin/env python3
"""
anti_ai_flavor/cli.py — CLI 入口

用法：
  anti-ai-flavor rewrite [file] [--scene default] [-o output] [--report] [--watermark] [--llm]
  anti-ai-flavor density [file]
  anti-ai-flavor check-docs <docs_dir>
  anti-ai-flavor detect [file] [--provider mock] [--json]
"""

import argparse
import json
import os
import sys
from pathlib import Path

from .core import rewrite_text, detect_density, detect_all
from .llm_detector import create_detector
from .scoring import rewrite_with_report, score_text
from .watermark import detect_watermark
from .llm_rewrite import llm_rewrite


def main():
    parser = argparse.ArgumentParser(description="Anti-AI-Flavor Rewriter")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # rewrite 子命令
    rewrite_parser = subparsers.add_parser("rewrite", help="重写文本")
    rewrite_parser.add_argument("file", nargs="*", help="输入文件路径（默认 stdin，支持多文件/glob）")
    rewrite_parser.add_argument("--scene", default="default", help="场景 pack")
    rewrite_parser.add_argument("--output", "-o", help="输出文件（默认 stdout，多文件时忽略）")
    rewrite_parser.add_argument("--diff", action="store_true", help="显示 diff")
    rewrite_parser.add_argument("--strict", action="store_true", help="严格模式：漏掉 Tier 1 词时报错")
    rewrite_parser.add_argument("--report", action="store_true", help="输出改写评分报告（JSON）")
    rewrite_parser.add_argument("--watermark", action="store_true", help="检测并清理水印/异常字符")
    rewrite_parser.add_argument("--llm", action="store_true", default=False, help="启用 LLM 后处理改写（默认关闭，需显式传入）")
    rewrite_parser.add_argument("--no-llm", action="store_true", help="关闭 LLM 后处理（默认已关闭，此参数保留用于兼容）")
    rewrite_parser.add_argument("--llm-model", default="glm-4-flash", help="LLM 模型（默认 glm-4-flash）")
    rewrite_parser.add_argument("--llm-base-url", default="https://open.bigmodel.cn/api/paas/v4", help="LLM base URL")

    # density 子命令
    density_parser = subparsers.add_parser("density", help="检测密度")
    density_parser.add_argument("file", nargs="?", help="输入文件路径（默认 stdin）")

    # check-docs 子命令
    check_parser = subparsers.add_parser("check-docs", help="检查目录下所有 markdown 文件的密度")
    check_parser.add_argument("docs_dir", help="文档目录路径")
    check_parser.add_argument("--fix", action="store_true", help="自动 rewrite 需要重写的文件")

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
        files = args.file or []

        def _process_raw(raw: str):
            # 水印预处理
            if args.watermark:
                wm_result = detect_watermark(raw, clean=True)
                if wm_result.warnings:
                    for w in wm_result.warnings:
                        print(f"ℹ️ 水印清理: {w}", file=sys.stderr)
                raw = wm_result.cleaned_text

            # 评分报告
            if args.report:
                rewritten, report = rewrite_with_report(raw, scene=args.scene)
            else:
                rewritten = rewrite_text(raw, scene=args.scene)
                report = None

            # LLM 后处理（默认关闭，显式传入 --llm 才启用）
            use_llm = args.llm and not args.no_llm
            if use_llm:
                try:
                    rewritten = llm_rewrite(
                        rewritten,
                        base_url=args.llm_base_url,
                        model=args.llm_model,
                        scene=args.scene,
                    )
                    if report is not None:
                        # LLM 成功后同步更新报告，避免 rewritten / score_after 与真实输出不一致
                        report["rewritten"] = rewritten
                        report["changed"] = True
                        score_after = score_text(rewritten)
                        report["score_after"] = {
                            "score": score_after.score,
                            "raw": score_after.raw,
                            "summary": score_after.summary,
                            "hits": [
                                {
                                    "category": h.category,
                                    "pattern_id": h.pattern_id,
                                    "matched_text": h.matched_text,
                                    "penalty": h.penalty,
                                    "note": h.note,
                                }
                                for h in score_after.hits
                            ],
                        }
                        report["llm_applied"] = True
                        report["llm_model"] = args.llm_model
                except (ValueError, ImportError, RuntimeError) as e:
                    print(f"⚠️ LLM rewrite 降级: {e}", file=sys.stderr)
                    # 不退出，继续用纯规则结果

            return rewritten, report

        if len(files) > 1:
            # 多文件模式：不支持 --diff/--report/--output/--strict
            for f in files:
                raw = Path(f).read_text(encoding="utf-8")
                rewritten, _ = _process_raw(raw)
                print(f"=== {f} ===")
                print(rewritten)
            sys.exit(0)

        if len(files) == 1:
            raw = Path(files[0]).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()

        rewritten, report = _process_raw(raw)

        # 输出
        if args.diff:
            import difflib
            diff_lines = difflib.unified_diff(
                raw.splitlines(keepends=True),
                rewritten.splitlines(keepends=True),
                fromfile=files[0] if files else "stdin",
                tofile=args.output or "stdout",
            )
            sys.stdout.writelines(diff_lines)
        elif args.output:
            Path(args.output).write_text(rewritten, encoding="utf-8")
            print(f"已写入: {args.output}", file=sys.stderr)
        else:
            if args.report and report is not None:
                output = {
                    "original": report["original"],
                    "rewritten": report["rewritten"],
                    "changed": report["changed"],
                    "score_before": report["score_before"],
                    "score_after": report["score_after"],
                }
                if report.get("llm_applied"):
                    output["llm_applied"] = True
                    output["llm_model"] = report["llm_model"]
                print(json.dumps(output, ensure_ascii=False, indent=2))
            else:
                print(rewritten)

        # 严格模式：检查 Tier 1 残留
        if args.strict:
            from .core import detect_tier1
            remaining = detect_tier1(rewritten)
            if remaining:
                for word, loc in remaining:
                    print(f"STRICT: 残留 Tier1「{word}」at {loc}", file=sys.stderr)
                sys.exit(3)

        if args.report and report is not None:
            score_before = report["score_before"]["score"]
            score_after = report["score_after"]["score"]
            print(f"📊 评分: {score_before} → {score_after}", file=sys.stderr)

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
        issue_files = []
        fixed_files = []
        for f in md_files:
            text = f.read_text(encoding="utf-8")
            result = detect_density(text)
            if result["should_rewrite"]:
                issues_found = True
                issue_files.append(f)
                print(f"\n⚠️ {f}:", file=sys.stderr)
                for w in result["warnings"]:
                    print(f"  - {w}", file=sys.stderr)
                if result["tier2_words"]:
                    print(f"  Tier 2 词: {', '.join(result['tier2_words'])}", file=sys.stderr)
                if result["tier3_words"]:
                    print(f"  Tier 3 词: {', '.join(result['tier3_words'])}", file=sys.stderr)

                if args.fix:
                    rewritten = rewrite_text(text)
                    if rewritten != text:
                        f.write_text(rewritten, encoding="utf-8")
                        fixed_files.append(f)
                        print(f"  ✅ 已自动 rewrite", file=sys.stderr)

        if issues_found:
            if args.fix and fixed_files:
                print(f"\n🔧 已修复 {len(fixed_files)} 个文档", file=sys.stderr)
            print(f"\n❌ {len(issue_files)} 个文档需要重写", file=sys.stderr)
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

        # mock 检测器标注
        is_mock = args.provider == "mock"
        mock_label = " (mock only)" if is_mock else ""

        if args.json:
            output = {
                "text": raw,
                "provider": args.provider,
                "mock_only": is_mock,
                "detections": [
                    {
                        "pattern_id": r.pattern_id,
                        "pattern_name": r.pattern_name,
                        "confidence": r.confidence,
                        "matched_text": r.matched_text,
                        "suggestion": r.suggestion,
                    }
                    for r in results
                ],
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            if not results:
                print(f"✅ 未检测到 AI 味特征{mock_label}")
            else:
                print(f"⚠️ 检测到 {len(results)} 个 AI 味特征{mock_label}：")
                for r in results:
                    print(f"  [{r.pattern_id}] {r.pattern_name} (置信度: {r.confidence:.0%})")
                    print(f"    匹配: {r.matched_text}")
                    print(f"    建议: {r.suggestion}")

        sys.exit(0 if not results else 2)


if __name__ == "__main__":
    main()
