# anti-ai-flavor 项目优化空间调查报告

> 日期：2026-09-22 | 作者：自动化代码评审 | 版本：v1.0

---

## 目录

1. [P0 — 必须修复（Bug / 风险）](#p0--必须修复bug--风险)
2. [P1 — 建议做（收益明显）](#p1--建议做收益明显)
3. [P2 — 可以做（改善质量）](#p2--可以做改善质量)
4. [P3 — 可选（锦上添花）](#p3--可选锦上添花)
5. [下一步行动计划](#下一步行动计划)

---

## P0 — 必须修复（Bug / 风险）

### P0-01：core.py 顶部重复导入 + 未使用导入

- **问题描述**：`src/anti_ai_flavor/core.py:8-10` 和 `core.py:14-16` 重复导入了 `import re`、`import sys`、`from pathlib import Path`。另外 `core.py:12-13` 的 `import argparse`、`import json` 在模块级别完全未使用（`argparse` 仅在 CLI 层使用，`json` 在 `_load_golden_whitelist()` 函数内又做了一次 `import json`，见 `core.py:804`）。
- **影响面**：无运行时错误，但违反 Python 最佳实践，lint 工具（ruff/flake8）会报 F811 redefinition / F401 unused import。首次加载模块时 `Path` 被导入两次（轻微性能影响）。
- **建议方案**：删除第 12-16 行整个重复导入块，`argparse` 移到 `cli.py`（已经在那里导入了），`json` 完全依赖函数内的惰性导入（或统一移到顶部）。
  ```python
  # 删除 core.py:12-16 行：
  # import argparse   <- 删除
  # import json       <- 删除（函数内已有 import json at line 804）
  # import re         <- 删除（重复）
  # import sys        <- 删除（重复）
  # from pathlib import Path  <- 删除（重复）
  ```
- **风险**：低 — 纯删除操作，不影响功能。只需确保 `json` 在 `_load_golden_whitelist()` 中确实有独立 `import`（已验证：`core.py:804`）。
- **预估工作量**：S（5 分钟）

---

### P0-02：CLI `--diff` 标志已定义但从未实现

- **问题描述**：`src/anti_ai_flavor/cli.py:34` 定义了 `rewrite_parser.add_argument("--diff", action="store_true", help="显示 diff")`，但在 `cli.py:64-143` 的 `main()` 函数中完全没有任何 `args.diff` 的引用。用户传 `--diff` 后输出与不传完全一致。
- **影响面**：用户看到 `--diff` 帮助信息后传参，但无任何 diff 输出，属于 UX 破损承诺。
- **建议方案**：实现 `--diff` 分支。在输出阶段（`cli.py:121-138` 附近），若 `args.diff` 为真，使用标准库 `difflib.unified_diff` 输出 unified diff 格式：
  ```python
  if args.diff:
      import difflib
      diff_lines = difflib.unified_diff(
          raw.splitlines(keepends=True),
          rewritten.splitlines(keepends=True),
          fromfile=args.file or "stdin",
          tofile=args.output or "stdout",
      )
      sys.stdout.writelines(diff_lines)
  ```
- **风险**：低 — 纯新增功能，不影响现有逻辑。需配合 golden 测试验证不改写行为。
- **预估工作量**：M（1-2 小时，含测试）

---

### P0-03：CLI `--strict` 标志已定义但从未实现

- **问题描述**：`src/anti_ai_flavor/cli.py:35` 定义了 `rewrite_parser.add_argument("--strict", action="store_true", help="严格模式：漏掉 Tier 1 词时报错")`，但在 `main()` 中完全没有任何 `args.strict` 的引用。
- **影响面**：同 P0-02，破损承诺导致用户困惑。
- **建议方案**：实现严格模式：在 `rewrite_text()` 后，对输出再次运行 `detect_tier1()`，若仍有命中则打印 stderr 警告并以非零退出码退出。
  ```python
  if args.strict:
      from .core import detect_tier1
      remaining = detect_tier1(rewritten)
      if remaining:
          for word, loc in remaining:
              print(f"STRICT: 残留 Tier1「{word}」at {loc}", file=sys.stderr)
          sys.exit(3)
  ```
- **风险**：低 — 纯新增功能，不影响现有逻辑。
- **预估工作量**：M（1-2 小时，含测试）

---

## P1 — 建议做（收益明显）

### P1-01：`score_text()` 在 CLI `--report` + LLM 成功后重复调用 4 次

- **问题描述**：`src/anti_ai_flavor/cli.py:99-113`，当 `--report` + `--llm` 成功时，`score_text(rewritten)` 被调用了 **4 次**分别取 `.score`、`.raw`、`.summary`、`.hits`。每次调用都完整运行 `_count_tier1_hits` + `_count_legacy_hits` + `_count_pattern_hits` 的 O(n×m) 正则扫描。
- **影响面**：大文本（>10KB）时 4x 正则扫描带来约 4 倍耗时。虽然 LLM 调用本身占大头，但纯规则路径下这是可避免的开销。
- **建议方案**：提取为单次调用：
  ```python
  score_result = score_text(rewritten)
  report["score_after"] = {
      "score": score_result.score,
      "raw": score_result.raw,
      "summary": score_result.summary,
      "hits": [
          {"category": h.category, "pattern_id": h.pattern_id,
           "matched_text": h.matched_text, "penalty": h.penalty, "note": h.note}
          for h in score_result.hits
      ],
  }
  ```
- **风险**：低 — 纯重构，逻辑等价。`ScoreResult` dataclass 已包含所有字段。
- **预估工作量**：S（15 分钟）

---

### P1-02：`core.py` 1114 行过长，应拆分为多个模块

- **问题描述**：`src/anti_ai_flavor/core.py` 共 1114 行，混合了 6 类职责：词库数据定义（lines 60-149）、25-pattern 改写管线（lines 158-429）、清理/合并函数（lines 434-548）、legacy fallback 改写（lines 552-697）、检测函数族（lines 699-791）、白名单逻辑（lines 795-821）、场景 auto-detect（lines 999-1051）、密度检测（lines 1052-1110）。当前 `score_text` 调用一次就需要导入整个文件的所有数据。
- **影响面**：代码导航困难，新增 pattern 容易改错文件。测试只能通过 `rewrite_text()` 间接覆盖内部函数。
- **建议方案**：
  - 新建 `src/anti_ai_flavor/rules.py` — 迁移 `TIER1_ZH`、`TIER1_EN`、`SYMMETRY_FILLERS`、`SUMMARY_CLOSERS`、`MECHANICAL_ORDERING`、`ABSTRACT_SUBJECTS`、`IDIOM_FILLERS` 等数据定义 + `EM_DASH_OVERUSE`
  - 新建 `src/anti_ai_flavor/cleanup.py` — 迁移 `_cleanup_residue()`、`_merge_sentences()`、`_final_cleanup()`
  - 新建 `src/anti_ai_flavor/detectors.py` — 迁移 `detect_tier1()` 到 `detect_em_dash()` 的 7 个检测函数 + `detect_all()` + `severity()`
  - 新建 `src/anti_ai_flavor/whitelist.py` — 迁移 `_load_golden_whitelist()`、`_is_golden_whitelisted()`
  - `core.py` 保留 `rewrite_text()`、`_rewrite_with_patterns()`、`_legacy_rewrite()`、`auto_detect_scene()`、`rewrite_file_with_auto_scene()`、`detect_density()`、`check_paragraph_density()`
- **风险**：中 — 涉及大量 import 重构，golden 测试必须保持 10/10 通过。建议拆分后立刻运行 `pytest tests/ -v` 验证。
- **预估工作量**：L（3-5 小时）

---

### P1-03：`Match` dataclass 在所有 25 个 pattern 文件中重复定义

- **问题描述**：25 个 pattern 文件（`src/anti_ai_flavor/patterns/p01_*.py` 到 `p25_*.py`）各自独立定义了完全相同的 `Match` dataclass（`start`、`end`、`matched_text`、`suggested_fix` 四个字段）。每个文件约 9 行样板代码，共 25×9 = 225 行重复定义。例如 `p01_not_x_but_y.py:13-18`、`p10_list_fatigue.py:15-20`。
- **影响面**：如需修改 `Match` 结构（如增加 `confidence` 字段），需改 25 个文件。已发生过字段不一致风险。
- **建议方案**：在 `src/anti_ai_flavor/patterns/__init__.py` 中定义一次 `Match`，各 pattern 文件 `from . import Match` 即可。__init__.py 已有的导出机制可直接利用。
- **风险**：低 — 纯重构，不改变行为。各文件 `from dataclasses import dataclass` + 内联 `class Match` 改为 `from . import Match`。
- **预估工作量**：M（1-2 小时，25 个文件批量修改）

---

### P1-04：TIER1 词表在 `core.py` 与 `tier1_legacy.py` 中重复且不一致

- **问题描述**：`src/anti_ai_flavor/core.py:60-66` 定义了 30 个 `TIER1_ZH` 词（包含「展示了」「反映了」「推动了」），而 `src/anti_ai_flavor/patterns/tier1_legacy.py:9-15` 定义了 27 个（不含这 3 个）。`_rewrite_with_patterns()` 使用 `LEGACY_TIER1_ZH`（来自 tier1_legacy，27 词），而 `_legacy_rewrite()` 使用模块级 `TIER1_ZH`（30 词）。结果：pattern 模式和 legacy fallback 模式使用不同的词表，行为不一致。
- **影响面**：同一个输入在两种代码路径下可能得到不同输出。检测函数 `detect_tier1()` 使用模块级 `TIER1_ZH`（30 词），但改写管线 `_rewrite_with_patterns()` 使用 legacy 的 27 词表——意味着检测到「展示了」但改写却没处理它。
- **建议方案**：将 `core.py` 中的 `TIER1_ZH`、`TIER1_EN` 删掉，改为 `from .patterns.tier1_legacy import TIER1_ZH, TIER1_EN`，统一数据源。legacy 词表中补充缺失的 3 个词（「展示了」「反映了」「推动了」）。
- **风险**：中 — 统一后行为变化可能导致 golden 测试结果变更。需先补充词表再跑 golden 测试确认。
- **预估工作量**：M（1-2 小时）

---

### P1-05：`golden_set.json` 在 `src/` 和 `tests/` 中重复维护

- **问题描述**：`src/anti_ai_flavor/golden_set.json` 和 `tests/golden_set.json` 内容完全相同（已验证 diff 为空）。`_load_golden_whitelist()` 在 `core.py:805` 读 `src/` 下的版本，`test_golden_set.py:23` 和 `test_detect_cases.py:142` 读 `tests/` 下的版本。修改一条 golden case 需要同步改两个文件。
- **影响面**：维护负担，未来 Golden 增加到 20-50 条时极易漏同步。
- **建议方案**：tests 代码统一读取 `src/anti_ai_flavor/golden_set.json`（通过 `importlib.resources` 或相对路径），删除 `tests/golden_set.json`。或反过来让 `_load_golden_whitelist()` 接受路径参数。
- **风险**：低 — 纯工程重构，不影响业务逻辑。
- **预估工作量**：S（30 分钟）

---

### P1-06：`_rewrite_with_patterns()` 中 Phase 2 LLM 检测代码块完全死代码

- **问题描述**：`src/anti_ai_flavor/core.py:417-427` 在 `_rewrite_with_patterns()` 末尾有一段 LLM 检测逻辑，但 `create_detector(enabled=False)` 的 `enabled=False` 是硬编码的，`detector.enabled` 永远为 `False`，整个 `if` 块永远不执行。此外 `core.py:52-55` 已尝试导入 `create_detector`，`core.py:418` 又重复导入了一次。
- **影响面**：代码腐化，增加维护者阅读负担。4 行导入 + 注释 + 空壳代码共约 12 行无用代码。
- **建议方案**：删除 `core.py:417-427` 整个代码块。若将来需要启用此功能，通过 `_rewrite_with_patterns` 增加 `enable_llm_detect: bool = False` 参数传递，而不是硬编码。
- **风险**：低 — 删除死代码，无行为变化。
- **预估工作量**：S（10 分钟）

---

### P1-07：缺少批量 rewrite 能力

- **问题描述**：从用户场景出发，用户常需要批量处理多个文件（如整个 docs/ 目录下所有 .md）。当前 `rewrite` 子命令（`cli.py:30-41`）只接受单个文件或 stdin，`check-docs`（`cli.py:161-190`）只做密度检测不执行 rewrite。用户需要写 shell 循环 `for f in docs/*.md; do anti-ai-flavor rewrite "$f" -o "$f"; done`。
- **影响面**：用户体验差，check-docs 检出问题后无法一键修复。
- **建议方案**：
  1. `rewrite` 子命令支持 glob 参数或多文件输入：`anti-ai-flavor rewrite docs/*.md`
  2. `check-docs` 增加 `--fix` 标志，对检测到的文件自动执行 rewrite。
  3. 需注意保守化白名单约束：批量 rewrite 对每个文件仅改写与 golden_set 完全匹配的段落，其他保持原样。这在批量处理时语义清晰（"只改你知道怎么改的"）。
- **风险**：中 — 核心功能变更，需仔细设计交互。golden 测试必须 10/10。
- **预估工作量**：L（4-6 小时）

---

### P1-08：`llm_detector.py` 导入了未使用的 core 函数

- **问题描述**：`src/anti_ai_flavor/llm_detector.py:18-22` 从 `.core` 导入了 `PATTERNS_AVAILABLE`、`rewrite_text`、`detect_density`，但在整个文件中这三个符号从未被使用。导入 `rewrite_text` 和 `detect_density` 还可能导致循环导入风险（core 反过来也 import llm_detector 的 create_detector）。
- **影响面**：无运行时影响但违反了 lint 规则，且增加循环导入隐患。
- **建议方案**：删除 `llm_detector.py:18-22` 中未使用的导入。
- **风险**：低 — 纯删除。
- **预估工作量**：S（5 分钟）

---

### P1-09：`_rewrite_with_patterns()` 内部惰性导入产生重复 import 开销

- **问题描述**：`src/anti_ai_flavor/core.py:379`、`core.py:384`、`core.py:389` 在 `_rewrite_with_patterns()` 函数体内分别执行 `from .patterns.tier1_legacy import IDIOM_FILLERS` / `DENSITY_FILLERS` / `REDUNDANT_MODIFIERS`。虽然 Python 的 import 缓存避免了重复加载模块，但每次 `_rewrite_with_patterns()` 调用仍执行 3 次属性查找（`sys.modules` 查表 + getattr）。
- **影响面**：高频调用场景下（如批量处理 100+ 文件）累积开销。更关键的是代码可读性差——数据源分散在函数体各处。
- **建议方案**：将这三个导入移到 `_rewrite_with_patterns()` 函数外、模块顶部（与 lines 18-48 的其他 pattern import 并列）。注意：这三个符号本身不在 `patterns/__init__.py` 的 `__all__` 中，需先检查是否可从 tier1_legacy 直接 import。
- **风险**：低 — 惰性导入非必要，因为 tier1_legacy 模块不依赖 core（已验证无循环导入）。
- **预估工作量**：S（15 分钟）

---

## P2 — 可以做（改善质量）

### P2-01：`scoring._count_pattern_hits()` 只覆盖 p01-p10，缺少 p11-p25

- **问题描述**：`src/anti_ai_flavor/scoring.py:179-189` 定义的 `pattern_groups` 列表仅包含 p01 到 p10 的正则模式。p11-p25 完全没有评分覆盖。这意味着改写后如果命中 p11-p25 的特征（如反问句、过度限定、虚假精确等），scoring 不会反映在分数中。
- **影响面**：评分不完整，用户看到高分但文本仍有未被评分的 AI 味特征。
- **建议方案**：为 p11-p25 各增加一条轻量级正则模式到 `pattern_groups`，或直接导入各 pattern 的 `match()` 函数并统计命中数（可通过 `result = pXX_match(text); penalty = len(result) * 2`）。
- **风险**：中 — 新增评分逻辑可能改变现有测试预期值，需调整 `test_scoring.py` 中的断言阈值。
- **预估工作量**：M（2-3 小时）

---

### P2-02：`check-docs` 未利用已读取的文件内容做 rewrite

- **问题描述**：`src/anti_ai_flavor/cli.py:171-183` 的 check-docs 循环中，`f.read_text(encoding="utf-8")` 读取文件后仅调用 `detect_density(text)`。当检测到需要重写时（`should_rewrite=True`），只打印警告而不执行 rewrite。这是一个「检测-修复」流程断裂——用户拿到警告后需要手动 rerun `rewrite` 命令。
- **影响面**：用户工作流被打断，需要两次命令。
- **建议方案**：增加 `--fix` 选项（参考 P1-07），当 `should_rewrite` 且 `--fix` 时自动重写文件。
- **风险**：低 — 渐进增强，默认不启用。
- **预估工作量**：M（1-2 小时，依赖 P1-07 的设计决策）

---

### P2-03：CI 仅测试 ubuntu-latest，缺失 Windows/macOS 覆盖

- **问题描述**：`.github/workflows/ci.yml` 中 `runs-on: ubuntu-latest`，矩阵仅覆盖 Python 版本，未覆盖操作系统。虽然项目是纯 Python 文本处理，但 `pathlib.Path` 在不同 OS 下行为有差异（路径分隔符、编码默认值等）。
- **影响面**：Windows 用户遇到 `Path.write_text(encoding="utf-8")` 相关问题时无法提前发现。当前 `core.py:804-806` 用 `Path(__file__).with_name("golden_set.json")` 读取资源文件，在 Windows 下可正常工作但缺少 CI 验证。
- **建议方案**：CI 矩阵增加 `os: [ubuntu-latest, windows-latest, macos-latest]`。macOS 和 Windows 测试可设为 `continue-on-error: true` 先监控稳定性。
- **风险**：低 — 仅 CI 配置变更，不影响代码。
- **预估工作量**：S（15 分钟）

---

### P2-04：`pyproject.toml` 版本号硬编码，无自动化发布流程

- **问题描述**：`pyproject.toml:7` 和 `src/anti_ai_flavor/__init__.py:25` 都硬编码 `version = "0.1.0"`。每次发版需手动改两处。没有 `version` 的单一数据源（single source of truth）。
- **影响面**：发布时容易漏改一处导致版本不一致。PyPI 发布前无自动化检查。
- **建议方案**：
  1. 使用 `importlib.metadata` 动态读取版本号（pyproject.toml → package metadata），__init__.py 中改为 `__version__ = importlib.metadata.version("anti-ai-flavor")`。
  2. 或在 CI 中增加版本一致性检查 step。
- **风险**：低 — Python 3.10+ 均支持 `importlib.metadata`。
- **预估工作量**：S（20 分钟）

---

### P2-05：README 未描述保守化白名单行为

- **问题描述**：`README.md` 中「快速开始」示例直接调用 `rewrite_text(text)`，暗示任何文本都可以改写。但实际上 `rewrite_text()` 仅对 `golden_set.json` 中精确匹配的 10 条输入执行改写，白名单外原样返回。这个关键设计决策（用户拍板于 2026-09-18）在 README 中完全未提及。
- **影响面**：新用户第一次使用时会困惑 "为什么我的文本没被改写"，产生 issue/困惑。
- **建议方案**：在 README 的「设计」部分之前增加「重要：保守化白名单」一节，说明：
  - `rewrite_text()` 仅改写与 golden_set.json 精确匹配的输入
  - 检测功能（`detect_all`/`detect_density`/`detect`）不受白名单限制
  - 如何扩展 golden_set.json（新增用例的方法）
- **风险**：低 — 仅文档，不涉及代码。
- **预估工作量**：S（15 分钟）

---

### P2-06：测试文件使用 `sys.path.insert` 而非标准 pytest 导入

- **问题描述**：`tests/test_golden_set.py:16`、`tests/test_regression.py:10`、`tests/test_detect_cases.py:14` 均使用 `sys.path.insert(0, str(Path(__file__).parent.parent / "src"))` 来导入包。这是非标准做法，在 `pip install -e .` 后可能因路径冲突导致导入不一致。
- **影响面**：测试导入路径与实际安装路径不一致时可能漏测。CI 中 `PYTHONPATH=src pytest tests/ -v` 通过环境变量覆盖了这个问题，但本地 `python tests/test_golden_set.py` 直接运行时依赖 sys.path hack。
- **建议方案**：统一使用 `pip install -e ".[dev]"` 后直接 `from anti_ai_flavor import ...` 的标准方式。删除所有 `sys.path.insert` 行。将 test 文件改为纯 pytest 风格。
- **风险**：低 — 不影响测试逻辑，仅改变导入方式。
- **预估工作量**：S（30 分钟）

---

## P3 — 可选（锦上添花）

### P3-01：缺少属性测试（property-based testing）

- **问题描述**：当前所有测试均为手写的 example-based 测试（固定的 in/out 对）。没有用 Hypothesis 等框架做属性测试，无法自动发现边界 case。例如：
  - 属性 "任何输入经 rewrite_text 后不应比输入长超过 2 倍"
  - 属性 "空字符串应返回空字符串"
  - 属性 "纯中文无害文本应不受改动（对于白名单内输入）"
  - 属性 "score_text 的分数应在 0-100 之间"（已有手写测试但未穷举）
- **影响面**：存在未被覆盖的边界漏洞（如特殊 Unicode、极长文本、只有标点的输入）。
- **建议方案**：引入 `hypothesis` 作为 dev 依赖，编写 5-10 条属性测试。
- **风险**：低 — 新增测试，不改变代码。
- **预估工作量**：M（2-3 小时）

---

### P3-02：缺少对 `llm_rewrite.py` 和 `llm_detector.py` 的单元测试

- **问题描述**：`tests/` 目录下没有 `test_llm_rewrite.py` 和 `test_llm_detector.py`。`llm_rewrite.py` 的 `llm_rewrite()` 函数（lines 20-94）涉及 API key 校验、HTTP 调用、异常处理等多条路径，但无测试覆盖。`MockLLMDetector`（`llm_detector.py:230-245`）虽有 mock 实现，但未被任何测试引用。
- **影响面**：LLM 相关代码的回归保护为零，重构时极易引入 bug。
- **建议方案**：新增测试文件：
  - `tests/test_llm_detector.py`：测试 `MockLLMDetector` 的 detect() 行为、`create_detector` 的 provider 路由、异常路径
  - `tests/test_llm_rewrite.py`：用 `unittest.mock.patch("openai.OpenAI")` 测试 api_key 缺失、成功调用、空返回等路径
- **风险**：低 — 纯新增测试。
- **预估工作量**：M（2-3 小时）

---

### P3-03：中英混合场景缺少针对性测试和规则

- **问题描述**：从用户实际使用场景出发，中英混合文本（如技术文档）是常见的 AI 生成场景——技术 doc 中混合中文叙述和英文术语。当前 golden_set 只有 TC010 一个中英混合用例（`golden_set.json:67-71`），且 pattern 规则主要面向纯中文或纯英文，缺乏中英混合句式的专项检测。例如：
  - "这个 feature 不仅提升了 performance，而且 also 改善了 UX" — 中英混杂的对称填充
  - "综上所述，the solution is robust and comprehensive" — 中英混杂的总结结尾
- **影响面**：中英混合场景下 AI 味检测和改写能力不足。
- **建议方案**：
  1. 增加 5-10 条中英混合 golden 用例
  2. pattern 规则中增加混合语言的正则模式（如 `SUMMARY_CLOSERS` 后面紧跟英文文本的情况）
- **风险**：中 — 新增规则可能影响现有 golden 测试预期。
- **预估工作量**：L（4-6 小时）

---

### P3-04：`watermark.py` 中同形字计数的近似逻辑不精确

- **问题描述**：`src/anti_ai_flavor/watermark.py:89-92` 的 `_replace_homoglyphs()` 中，循环遍历 `_HOMOGLYPH_MAP` 后 `count += text.count(dst)` 使用目标字符出现次数近似计数，而不是实际替换数。例如文本中已有正常半角 "A"，替换全角 "Ａ" 后 `dst.count("A")` 会多算原来就有的 "A"。
- **影响面**：日志中 `homoglyph_replaced` 数字可能不准确，但不影响清理结果（文本内容正确）。
- **建议方案**：改为每次替换前统计具体替换次数：
  ```python
  for src, dst in _HOMOGLYPH_MAP.items():
      occurrences = text.count(src)
      if occurrences:
          text = text.replace(src, dst)
          count += occurrences
  ```
- **风险**：低 — 不影响清理逻辑，仅修正计数。
- **预估工作量**：S（10 分钟）

---

### P3-05：决策层面建议 — 评估 `--llm` 默认策略对 `detect` 子命令的影响

- **问题描述**：根据设计决策 2（LLM 默认关闭），`rewrite` 的 `--llm` 默认 `False`。但 `detect` 子命令（`cli.py:193-232`）也走相同的 `create_detector(enabled=True, provider=args.provider)`，且 `--provider` 默认值是 `"mock"`（`cli.py:54`）。这意味着 `detect` 命令默认返回 mock 结果（仅检测「值得注意的是」一条规则），用户可能误以为是真实的 AI 检测能力。
- **影响面**：`detect` 命令的默认行为与实际宣传不符。用户需要显式 `--provider openai` 或 `--provider anthropic` 才能获得真实检测。
- **建议方案**：
  1. 将 `--provider` 的默认值从 `"mock"` 改为 `"openai"`（并在文档中说明需要 API key），或
  2. 在 `detect` 子命令输出中明确标注「当前使用 mock 检测器，结果仅供参考」
  3. 考虑将 provider 默认值保持 `mock` 但在输出中增加 `(mock only)` 标识
- **风险**：中 — 改变默认行为可能影响依赖 `detect` 命令的脚本。
- **预估工作量**：S（20 分钟）

---

## 下一步行动计划

按 ROI 从高到低，建议优先做以下 3 件事：

| 优先级 | 行动 | 理由 |
|--------|------|------|
| **1** | 修复 P0-01（重复导入）+ P0-02/03（--diff/--strict 实现）+ P1-01（score_text 4x 调用） | 三个改动总计 < 3h，消除所有死代码和破损承诺，显著改善代码质量和用户体验。无风险，不影响 golden 测试。 |
| **2** | P1-03（Match 去重）+ P1-04（TIER1 统一）+ P1-05（golden_set 去重） | 消除三大数据源重复问题，是后续所有重构的基础。总工作量约 3-4h，改动集中在 pattern 文件和词表，可控。 |
| **3** | P1-07（批量 rewrite）+ P2-02（check-docs --fix） | 从用户场景出发，这是功能缺口中最直接影响用户体验的两个需求。完成后用户可实现 `anti-ai-flavor check-docs ./docs --fix` 一键检测+修复。 |

---

> **统计**：本报告共 21 条建议（P0: 3 / P1: 9 / P2: 6 / P3: 4），覆盖架构与代码质量、功能缺口、性能、测试、打包与发布、文档、兼容性 7 个维度。所有建议均附具体文件/行号/函数名引用，P0/P1 建议均含具体修改方案。