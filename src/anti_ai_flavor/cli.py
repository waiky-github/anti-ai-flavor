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
from .profiles import resolve_profile
from .profiles.detector import detect_scene
from .scoring import rewrite_with_report, score_text
from .watermark import detect_watermark
from .llm_rewrite import llm_rewrite


def main():
    parser = argparse.ArgumentParser(description="Anti-AI-Flavor Rewriter")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # rewrite 子命令
    rewrite_parser = subparsers.add_parser("rewrite", help="重写文本")
    rewrite_parser.add_argument("file", nargs="*", help="输入文件路径（默认 stdin，支持多文件/glob）")
    rewrite_parser.add_argument(
        "--scene",
        default="auto",
        help=(
            "场景：auto=按文本自动识别（默认，2026-10-26）；"
            "也可显式指定 social-note / health-content / tech-doc / base，"
            "旧别名（creative_doc / coder_pr / coder_commit …）仍可用。"
        ),
    )
    rewrite_parser.add_argument(
        "--no-auto-scene",
        action="store_true",
        help="强制按 base 底座处理，跳过场景识别（等价旧版 --scene default）",
    )
    rewrite_parser.add_argument(
        "--gate",
        action="store_true",
        help=(
            "CI 闸门模式：按场景判定的动作分档决定退出码——"
            "block 退出码 2（拒绝）、warn 退出码 1（需人工看），pass/rewrite 退出码 0。"
            "warn/block 时不会输出改写结果。"
        ),
    )
    rewrite_parser.add_argument(
        "--force",
        action="store_true",
        help="合规 block 时仍强制改写（默认拒绝改写：改写掩盖不了合规字面问题）",
    )
    rewrite_parser.add_argument("--output", "-o", help="输出文件（默认 stdout，多文件时忽略）")
    rewrite_parser.add_argument("--diff", action="store_true", help="显示 diff")
    rewrite_parser.add_argument("--strict", action="store_true", help="严格模式：漏掉 Tier 1 词时报错")
    rewrite_parser.add_argument("--report", action="store_true", help="输出改写评分报告（JSON）")
    rewrite_parser.add_argument("--watermark", action="store_true", help="检测并清理水印/异常字符")
    rewrite_parser.add_argument("--llm", action="store_true", default=False, help="启用 LLM 后处理改写（默认关闭，需显式传入）")
    rewrite_parser.add_argument("--no-llm", action="store_true", help="关闭 LLM 后处理（默认已关闭，此参数保留用于兼容）")
    rewrite_parser.add_argument("--llm-model", default=None, help="LLM 模型（默认 ANTI_AI_LLM_MODEL env → MiniMax-M3）")
    rewrite_parser.add_argument("--llm-base-url", default=None, help="LLM base URL（默认 ANTI_AI_LLM_BASE_URL env → https://api.minimaxi.com/v1）")
    rewrite_parser.add_argument(
        "--strategy",
        choices=["rules", "rules+llm", "llm-only", "auto"],
        default="rules",
        help=(
            "改写策略（2026-09-28 新增）："
            "rules=仅规则（默认，向后兼容）；"
            "rules+llm=规则清洗后 LLM 后处理（推荐工作流，需要 ANTI_AI_LLM_API_KEY）；"
            "llm-only=直接 LLM（跳过规则，需要 ANTI_AI_LLM_API_KEY）；"
            "auto=按 score_text 评分自动决策（score < llm_trigger_threshold 时触发 LLM）。"
        ),
    )
    rewrite_parser.add_argument(
        "--llm-trigger-threshold",
        type=int,
        default=70,
        help="--strategy auto 模式下，score_text 评分低于此值时触发 LLM 兜底（默认 70）",
    )
    rewrite_parser.add_argument(
        "--project-context",
        default=None,
        help=(
            "项目细节（自由文本），LLM 改写时参考补「叙事性描述」。"
            "例：「AI 平台项目是 5 人团队 3 个月搭起来的，业务方是国内 TOP 3 存储厂商，"
            "上线后推理 QPS 从 200 提到 1500」"
        ),
    )
    rewrite_parser.add_argument(
        "--project-context-file",
        default=None,
        help="从文件读取项目细节（每行一段，纯文本）。优先级低于 --project-context",
    )
    rewrite_parser.add_argument(
        "--project-sections-file",
        default=None,
        help=(
            "从 JSON 文件读取按段落标题精细控制的项目细节。"
            "格式: {\"段标题1\": \"细节1\", \"段标题2\": \"细节2\"}"
            "LLM 改写到对应段落时使用对应细节。"
        ),
    )

    # density 子命令
    density_parser = subparsers.add_parser("density", help="检测密度")
    density_parser.add_argument("file", nargs="?", help="输入文件路径（默认 stdin）")

    # check-docs 子命令
    check_parser = subparsers.add_parser("check-docs", help="检查目录下所有 markdown 文件的密度")
    check_parser.add_argument("docs_dir", help="文档目录路径")
    check_parser.add_argument("--fix", action="store_true", help="自动 rewrite 需要重写的文件")

    # scene 子命令（2026-10-26: 场景自动识别预览，只读）
    scene_parser = subparsers.add_parser(
        "scene", help="预览场景自动识别结果（只读，打印置信度与证据）"
    )
    scene_parser.add_argument("file", nargs="?", help="输入文件路径（默认 stdin）")
    scene_parser.add_argument("--json", action="store_true", help="JSON 输出")
    scene_parser.add_argument(
        "--force-scene", default=None, help="不识别，直接查指定场景的 profile 详情"
    )

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

        def _apply_llm_postprocess(text: str, report_dict: dict | None) -> tuple[str, dict | None]:
            """对规则清洗后的文本做 LLM 兜底；失败 fallback 到原文本。

            返回 (rewritten, updated_report)。report_dict 为 None 时不更新报告。
            """
            # 解析项目细节：--project-context > --project-context-file
            project_context = args.project_context
            if project_context is None and args.project_context_file:
                try:
                    project_context = Path(args.project_context_file).read_text(
                        encoding="utf-8"
                    ).strip()
                except OSError as exc:
                    print(
                        f"⚠️ 读取 --project-context-file 失败: {exc}",
                        file=sys.stderr,
                    )
                    project_context = None

            # 解析按段落标题的项目细节
            project_sections = None
            if args.project_sections_file:
                try:
                    raw = Path(args.project_sections_file).read_text(
                        encoding="utf-8"
                    )
                    project_sections = json.loads(raw)
                    if not isinstance(project_sections, dict):
                        raise ValueError("JSON must be an object")
                except (OSError, json.JSONDecodeError, ValueError) as exc:
                    print(
                        f"⚠️ 解析 --project-sections-file 失败: {exc}",
                        file=sys.stderr,
                    )
                    project_sections = None

            try:
                llm_result = llm_rewrite(
                    text,
                    base_url=args.llm_base_url,
                    model=args.llm_model,
                    scene=resolved["scene"],
                    project_context=project_context,
                    project_sections=project_sections,
                )
            except (ValueError, ImportError, RuntimeError) as exc:
                print(f"⚠️ LLM rewrite 降级: {exc}", file=sys.stderr)
                return text, report_dict

            if report_dict is not None:
                report_dict["rewritten"] = llm_result
                report_dict["changed"] = True
                score_after = score_text(llm_result)
                report_dict["score_after"] = {
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
                report_dict["llm_applied"] = True
                report_dict["llm_model"] = args.llm_model
            return llm_result, report_dict

        # 本次运行生效的场景（多文件时逐文件覆盖；LLM 兜底读这里）
        resolved = {"scene": "base", "info": None}

        def _resolve_scene_for(raw: str, path: str | None) -> str:
            """决定本次文本用哪个场景：显式指定 > 自动识别 > base 兜底。

            低置信不硬猜：交互终端下问一句；非交互（管道/CI/网关）下
            明确提示候选并回落 base，绝不静默按猜测处理。
            """
            if args.no_auto_scene or args.scene in ("default", "base"):
                return "base"
            if args.scene != "auto":
                return resolve_profile(args.scene).name

            guess = detect_scene(raw, path)
            resolved["info"] = guess
            if not guess.needs_confirmation:
                print(
                    f"🎯 场景自动识别: {guess.scene}（置信 {guess.confidence:.2f}）",
                    file=sys.stderr,
                )
                return guess.scene

            cand = guess.guessed_scene
            if cand and sys.stdin.isatty():
                try:
                    answer = input(
                        f"❓ 场景识别没把握（候选 {cand}，置信 {guess.confidence:.2f}）。"
                        f"按 {cand} 处理？[y/N] "
                    )
                except EOFError:
                    answer = ""
                if answer.strip().lower().startswith("y"):
                    return resolve_profile(cand).name
                print("ℹ️ 按 base 底座处理", file=sys.stderr)
                return "base"

            hint = f"，最像 {cand}" if cand else ""
            print(
                f"⚠️ 场景识别置信不足（{guess.confidence:.2f}）{hint}：按 base 处理。"
                f"如需指定请加 --scene <场景>",
                file=sys.stderr,
            )
            return "base"

        def _enforce_action(raw: str, scene: str) -> None:
            """第 3 层：按场景动作分档决定是改写、只警告还是拒绝。"""
            sc = score_text(raw, scene=scene)
            resolved["action"] = sc.action
            resolved["compliance_hit"] = sc.compliance_hit

            if sc.compliance_hit and not args.force:
                ids = {h.pattern_id for h in sc.hits
                       if h.pattern_id in resolve_profile(scene).compliance_patterns}
                # 跨场景命中的合规红线不在 hits 里（罚分不吃），单列出来，
                # 否则提示里会出现「（，场景 social-note）」这种空 id。
                ids.update(sc.details.get("compliance_cross_scene") or [])
                print(
                    f"⛔ 合规红线命中（{', '.join(sorted(ids))}，场景 {scene}）：拒绝自动改写。"
                    f"自动改写掩盖不了字面问题，请人工改。确需改写加 --force。",
                    file=sys.stderr,
                )
                sys.exit(2)

            if args.gate:
                if sc.action == "block":
                    print(
                        f"⛔ block（场景 {scene}，分数 {sc.score} ≤ block_at）："
                        f"机器改不动，交人工。",
                        file=sys.stderr,
                    )
                    sys.exit(2)
                if sc.action == "warn":
                    print(
                        f"⚠️ warn（场景 {scene}，分数 {sc.score}）：需人工过一眼，"
                        f"不输出改写结果。",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            if sc.action == "block":
                print(
                    f"⚠️ 分数 {sc.score} 偏低（场景 {scene}，action=block）："
                    f"改写结果仅供参考，建议人工复核。",
                    file=sys.stderr,
                )

        def _process_raw(raw: str):
            # 场景识别 + 动作闸门（2026-10-26 三层架构第 2/3 层）
            scene = _resolve_scene_for(raw, files[0] if files else None)
            resolved["scene"] = scene
            _enforce_action(raw, scene)

            # 水印预处理
            if args.watermark:
                wm_result = detect_watermark(raw, clean=True)
                if wm_result.warnings:
                    for w in wm_result.warnings:
                        print(f"ℹ️ 水印清理: {w}", file=sys.stderr)
                raw = wm_result.cleaned_text

            # 评分报告
            if args.report:
                rewritten, report = rewrite_with_report(raw, scene=scene)
            else:
                rewritten = rewrite_text(raw, scene=scene)
                report = None

            # 决定 LLM 兜底策略
            strategy = args.strategy
            # 向后兼容：显式 --llm 等价于 rules+llm
            if args.llm and not args.no_llm:
                if strategy == "rules":
                    strategy = "rules+llm"
            # --no-llm 始终覆盖（即使显式传了 --strategy rules+llm）
            if args.no_llm:
                strategy = "rules"

            if strategy == "rules":
                pass  # 仅规则，无 LLM
            elif strategy == "rules+llm":
                rewritten, report = _apply_llm_postprocess(rewritten, report)
            elif strategy == "llm-only":
                try:
                    llm_result = llm_rewrite(
                        raw,
                        base_url=args.llm_base_url,
                        model=args.llm_model,
                        scene=scene,
                    )
                    rewritten = llm_result
                    if report is not None:
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
                except (ValueError, ImportError, RuntimeError) as exc:
                    print(f"⚠️ LLM rewrite 降级: {exc}", file=sys.stderr)
            elif strategy == "auto":
                # 先规则清洗；评分仍低于阈值时调 LLM
                pre_score = score_text(rewritten).score
                if pre_score < args.llm_trigger_threshold:
                    print(
                        f"🤖 auto 触发 LLM 兜底（规则后 score={pre_score} < {args.llm_trigger_threshold}）",
                        file=sys.stderr,
                    )
                    rewritten, report = _apply_llm_postprocess(rewritten, report)
                else:
                    print(
                        f"✅ auto 跳过 LLM（规则后 score={pre_score} >= {args.llm_trigger_threshold}）",
                        file=sys.stderr,
                    )

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
                output["scene"] = resolved["scene"]
                if resolved.get("info") is not None:
                    output["scene_confidence"] = round(resolved["info"].confidence, 3)
                output["action"] = resolved.get("action")
                output["compliance_hit"] = bool(resolved.get("compliance_hit"))
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

    # scene 子命令
    elif args.command == "scene":
        if args.file:
            raw = Path(args.file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()

        if args.force_scene:
            prof = resolve_profile(args.force_scene)
            info = {
                "requested": args.force_scene,
                "resolved": prof.name,
                "label": prof.label,
                "description": prof.description,
                "policy": prof.policy.to_dict(),
                "compliance_patterns": list(prof.compliance_patterns),
                "disabled_patterns": list(prof.disabled_patterns),
                "extra_patterns": list(prof.extra_patterns),
                "penalty_overrides": dict(prof.penalty_overrides),
            }
        else:
            info = detect_scene(raw, args.file).to_dict()
            prof = resolve_profile(info["scene"])
            info["label"] = prof.label
            info["policy"] = prof.policy.to_dict()
            info["compliance_patterns"] = list(prof.compliance_patterns)

        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"🎯 场景: {info.get('scene')} → {info.get('label') or ''}")
            if "confidence" in info:
                print(f"   置信度: {info['confidence']:.2f}"
                      f"（{'可信' if not info['needs_confirmation'] else '没把握，需追问'}）")
                if info.get("guessed_scene"):
                    print(f"   最像: {info['guessed_scene']}")
                print(f"   证据: {'; '.join(info['evidence']) or '无'}")
                print(f"   分数: {info['scores']}")
            print(f"   动作分档: {info['policy']}")
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
