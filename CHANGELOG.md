# Changelog

All notable changes to anti-ai-flavor are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

---

## [0.2.18] - 2026-10-26

把「人写 + 反复打回重写」的 9 版经验固化成可复用判定体系：检测、判定、处置、改写四层拆开，检测层只管「有没有 AI 味」，判定层按场景决定扣多少分，处置层给出 pass / warn / rewrite / block 四档动作，改写层兜底。核心目的是让这个库能当发布前的强制闸门用，而不是只能事后打分。

> 记录缺口：0.2.16、0.2.17 两次版本号 bump 没有留下 CHANGELOG 条目，本版一并说明，历史细节待补。

### Added

#### 1. 12 个新 pattern（p28-p40）

p28 身体反应、p29 金句收尾、p30 分阶段坦白、p31 假身份代入、p32 模板枚举、p33 对比否定、p34 破折号滥用、p35 医疗功效、p36 绝对化用语、p37 替代医生、p38 空洞升华、p39 三段排比、p40 营销话术。pattern 总数 25 → 40。

#### 2. `profiles/` 场景判定包

- `base`：只覆盖任何场景都不该出现的表达（85/70/55）
- `social-note`：小红书语域，口语化 p27 不扣分，模板枚举与营销话术计入（85/68/50）
- `health-content`：医疗合规口径，p35/p37 为合规红线，跨场景也拦（90/75/65）
- `tech-doc`：允许必要枚举与命令（85/70/55）

`ActionPolicy.decide` 按分数带出动作；合规命中无视分数直接 block。

#### 3. 场景识别器 `detect_scene`

按语域特征打分并给出证据链，实测小红书样本文本置信度 0.92-0.97，证据形如 `emoji +2.0 / 第一人称叙事 +2.0 / 亲历动作 +1.0`。

#### 4. CLI `scene` 子命令 + 闸门模式

- `anti-ai-flavor scene note.md`：只读预览识别结果
- `rewrite --scene auto`（默认）/ `--no-auto-scene` / `--gate` / `--force`
- gate 模式退出码：block → 2（且不输出改写）、warn → 1、pass/rewrite → 0

#### 5. 场景化 LLM prompt 增量

`SCENE_PROMPT_DELTAS` 按场景注入；实测 auto 分支 system prompt 2003 字符 vs base 1788 字符。

### Fixed

#### 1. 改写把段落全压平（15 段变 4 段）

根因两处：`_cleanup_residue` 里 `re.sub(r"[\s]+", " ", text)` 折叠所有空白；标点后合并规则用 `\s+` 把换行也吃掉。修法：入口把段落分隔与段内断行换成私用区哨兵、出口原样还原，合并规则改为只吃空格与制表符 `[ \t]+`。修复后 v3/v5/v8/v9 四个版本改写均逐字幂等，段数行数零变化。

#### 2. 库 API `scene="auto"` 静默回落 base

`resolve_profile("auto")` 认不出 `auto` 这个 key，悄悄用 base 判定，导致同一文本 CLI 判 32 分 block、库判 44 分 block，且无从发现。新增 `resolve_profile_for_text(scene, text)` 真跑场景识别；未知场景名改为发 `RuntimeWarning` 并列出可用场景，杜绝静默 fallback。

#### 3. 网关合规日志打印无关 pattern

合规闸门命中时日志把全部 hits 都列为原因，实测出现 `p27_over_colloquial` 这种与合规无关的条目，排障会被带偏。改为只列真正触发合规判定的 pattern id（含跨场景判定结果）。

#### 4. 测试隔离：34 个用例连锁失败

两个测试文件的 `_run` 辅助函数用 `asyncio.get_event_loop()`，同进程内先跑过 `asyncio.run` 的用例会把线程 current loop 置空，后续抛 `RuntimeError: There is no current event loop`。改为统一用 `asyncio.run`。

### Changed

- `__all__` 补上 `resolve_profile_for_text`、`cross_domain_compliance`（此前导出缺失，静态检查报 unknown import symbol）
- README 删掉已废弃的「仅 golden_set.json 白名单输入可改写」段，改为四层架构 / 场景表 / 动作分档 / `--gate` 用法；白名单行为仍在，但默认关闭，需显式 `whitelist_strict=True` 开启

### 测试覆盖

`pytest tests/ -q` → 380 passed。新增 10 个测试文件，覆盖场景 profile、场景识别器、动作分档、网关场景接线、网关合规闸门、LLM 场景 prompt 增量、空白保真、pattern 缺口、库 API auto 语义。

验收脚本 `scripts/acceptance_scene_2026_10_26.py`：对抗样本 13/13 命中、负样本 10/10 零命中、版本分数 32 → 85 → 100 → 100 单调。

---

## [0.2.15] - 2026-09-30

v0.2.13/14 prompt 加「准正式技术写作」后实测发现：LLM 把 v8 简历段 845 字扩写到 988-1021 字（+11~21%），违背「不发明事实」原则。「补项目落地叙事」原条款鼓励扩写，与长度目标冲突。

### Changed

#### 1. llm_rewrite.py SYSTEM_PROMPT 收紧（src/anti_ai_flavor/llm_rewrite.py）

新增「长度约束」段：
- 输出总字数与原文偏差控制在 ±10% 以内
- 短文（100-300 字）禁止补「项目细节」扩写
- 长文（300 字+）只压缩冗余、拆长句，不补叙事
- 禁止「面向 XX 场景/解决 XX 问题」类模板化叙事（除非原文已有）

删除原「关键原则 3」：
- ~~补项目落地叙事：每个成果后面加 1 句「面向 XX 场景/解决 XX 问题」~~
- v0.2.13 的 GPU 部署 few-shot 例也撤了（鼓励模型编参数）

#### 2. 模块版本号

llm_rewrite.py 加 `__version__ = "0.2.15"`，方便 verify 工具记录回写路径。

### 测试覆盖

TBD — 本版侧重 prompt 调整，pytest 维持 144 passed。

---

## [0.2.14] - 2026-09-30

v0.2.12/v0.2.13 修复后跑用户实测发现两个独立问题：

### Changed

#### 1. tier1_zh 进一步拆分（patterns/tier1_legacy.py）
- **移除「驱动」「体系」「支撑」「模式」** 4 个词（v0.2.12 已移除「链路」「机制」）
- 这四个词在工程语境下同样是常用术语（"事件驱动""监控告警体系""后端支撑""Observer 模式"），
  与 AI 味儿的"数据驱动方法推动""指标体系建设""业务支撑""业务模式"无法用规则区分
- TIER1_ZH 词数：28 → 24，剩余都是「绝对不能写」的纯套话/AI 腔过渡词

#### 2. score 公式 bug 修复（scoring.py）
- **旧 bug**：raw=2 + chars=129 → norm=15.5 → score=60（短文本 1 个 hit 直接砍 40 分）
- **新公式**：`raw ≤ 5` 时 score 下限保护 85
  - raw ≤ 5 表示「规则只是抓到几个小毛病，不算 AI 味文本」，保护下限 85
  - raw > 5（≥6 个扣分点）说明是真正 AI 味文本，让 sqrt 全权发挥
- 公式保持 sqrt 衰减，但加一道「轻命中保护」

### 测试覆盖
- 新增 `tests/test_tier1_zh_tech_words_v2.py`（11 用例）：
  - 驱动/体系/支撑/模式 各不扣分
  - 纯工程师文本（含 Kafka 事件驱动/Observer 模式/对账支撑）≥95
  - AI 味儿文本仍 <80
  - TIER1_ZH 词数 = 24
  - 公式边界：raw=0 → 100, raw=2 短文 ≥85, 重度 AI <80
- 更新 `tests/test_tier1_zh_tech_words_fix.py` 词数断言 28 → 24
- pytest **144 passed**（原 133 + 11 新增）

### 端到端实测
- v8_raw AI 味长文 (raw=14)：score 31 → 仍受 sqrt 衰减保护底层（轻度扣分因词移走）
- v9_golden 工程师叙事标答 (raw=0)：score 100 → 满分（无损）
- 短文 1 个 p05 hit (raw=2)：score 60 → **85**（bug 修复）✅
- 重度 AI 味 (raw=17)：score 0 → 仍 0（保护不触发）
- 中度 AI 味 (raw=2)：score 64 → 85（提升）

---

## [0.2.13] - 2026-09-30

LLM 改写 prompt 收口"老炮儿"腔。用户实测批评 v0.2.12 输出「我们给客户的业务系统做整体方案。做了几年这行，手里有一些落地案例，客户那边的反馈还行」像聊天不像工程师。

### Changed

#### llm_rewrite.py SYSTEM_PROMPT 收紧
- 「真人资深工程师」 → 「资深工程师/技术作者」
- 「搭了/做出来/跑起来/打通/手撕/搞定」改为"避免项"
- few-shot 4 组对照全部改为准正式（清华理工/字节技术博客风格）：
  - 旧：「把测试、发布几个流程接到同一个平台，不用再分别登系统」
  - 新：「将测试、发布、资源申请等流程统一接入同一平台，避免在多系统间切换」
- 抽象→具体动词对照：「搭了/做了」→「建设/搭建/开发」
- 语调：「动词/结果用口语」→「准正式技术写作风格：陈述句为主，书面词汇为主」
- 「少用"我""咱们"，多用"本项目""该模块""系统侧"」

#### 测试覆盖
- 新增 3 个反向断言：
  - `test_prompt_contains_concrete_verb_rules`：必须含"建设/搭建/开发"
  - `test_prompt_avoids_colloquial_examples`：few-shot 与动词对照不含「搭了/做出来/跑起来/打通/手撕/搞定」
  - `test_prompt_formal_tone_directive`：必须含"准正式"
- pytest **133 passed**（原 131 + 2 新增；v0.2.13 没有新增独立文件）

### 端到端实测
- 实例 3 营销文案：v0.2.12「手里有一些落地案例，客户那边的反馈还行」 → v0.2.13「相关产品在客户中获得了稳定的口碑反馈，能够支持其在具体业务场景下完成成本与效率方面的优化」

---

## [0.2.12] - 2026-09-30

v0.2.11 重跑四方对比时发现 v9_golden 标答因「链路」「机制」被 tier1_zh 误伤 10 分。移走这两个工程师正常用词（"链路追踪""缓存机制""告警机制"等），「模式」保留（AI 文本「业务模式/营销模式」空洞搭配多）。

### Changed

#### tier1_zh 拆分（patterns/tier1_legacy.py）
- **移除**「链路」「机制」两项：工程师/产品语境中是常用术语，真人技术文本不该被扣分；改由密度判定（density/红海词组合）兜底
- 「模式」暂留：因 AI 文本「业务模式/营销模式/增长模式」空洞搭配多，靠密度敏感
- TIER1_ZH 词数：30 → 28

#### 测试覆盖
- 新增 `tests/test_tier1_zh_tech_words_fix.py`（5 用例）：「链路」「机制」不扣分、纯工程师文本 ≥95、AI 味文本仍 <80、TIER1_ZH 词数=28
- pytest **131 passed**（原 126 + 5 新增）

#### 端到端验证
- v9_golden 工程师叙事标答 score 73 → 100（+27），误伤彻底修掉
- v8_raw score 20 → 31（+11），同样受益
- LLM 改写耗时 49.8s（minimax-CN MiniMax-M3, max_tokens=8000）

---

## [0.2.11] - 2026-09-28

对比 deepseek 去 AI 味儿效果后的「AI 味还是太浓」反馈，按优先级做三项治理（A→B→C）。121 tests 全绿，周报体实测验证黑话全清 + 事实守恒 10/10。

### Changed

#### A. 评分器（scoring.py）
- **千字密度归一化**：`norm_penalty = raw_penalty × 1000 / char_count` 取代旧 sqrt 累加，长文不再因篇幅天然吃罚
- **p05/p10 精细化**：抽象词拆强黑话（赋能/闭环/全方位/数智化…）与弱正常词（优化/交付/核心…）两档，强黑话 ≥1 即抓，无强黑话须整串全为空洞宣称才抓
- **details 增字段**：`norm_penalty` / `hits_per_1k` / `char_count`
- 修复简历技术列举（功能/性能/系统测试）从大面积误伤恢复 100 分

#### B. 结构层去重（dedup.py，新增）
- 段落级精确 + 近似（difflib，默认 0.90）去重，保留首版
- `_strip_workpaper()` 剥离 `<think>` 块 / 英文工作底稿 / ✓✗ 勾选行，保留中文正文与技术名词
- 已集成进 `llm_rewrite`（pattern 预清洗前执行），新增 `dedup` / `dedup_similarity` 开关
- 实证：判「误删」前先定位 `</think>` 闭合标签——大文件可能整块是思维链，成稿在闭合标签之后，字符数对不上不等于误删

#### C. prompt 真人化（llm_rewrite.py SYSTEM_PROMPT）
- 禁词补：数智化 / 数字化转型 / 智能化转型 / 数智化转型（要求换成具体做了什么）
- 从绝对禁词表移除：优化 / 升级 / 实现 / 推动（工程师正常词，一刀切禁反而假）
- 新增「真人 vs AI 句对照」few-shot（4 组对照）
- 新增「不要硬删」白名单：架构/流程/规范/模块/场景/体系/落地/核心/持续；「项目全生命周期管理」按语境判；「优化/提升/实现」带具体对象+数字可保留

### Verified

- 简历体（v8 于凯简历，44K 含 think）：剥离后成稿 2103 字完整真实，无重复板块
- 周报体（500 字 W39 周报，含数智化转型/全方位赋能/全生命周期解决方案）：真实 API（ark plan deepseek-v4-flash）改写后黑话 11/11 清除，事实守恒 10/10（4×A100 80GB / vLLM / Qwen3.6-27B / FP8 / TP=4 / MTP / 200 人 / W39 / P0 / 30 分钟 全保留）
- AI score 7 → 63（Δ +56），professionalism 85 → 84（口语化代价，specificity 64→72 升）
- 121/121 tests passed

### Notes

- deepseek-v4-flash 推理型 ~136 tok/s，单段验证 timeout 需 280s+，默认 120s 必炸
- prompt 验证脚本里显式传 api_key/base_url/model 比依赖环境变量可靠（裸 shell 里 `ANTI_AI_LLM_API_KEY` 常未注入）
- 已知小瑕疵：原句无数字时概率性残留「效率提升明显」这种空洞尾句，值得但不重烧一次的边际成本

---

## [0.2.10] - 2026-09-28

LLM 兜底管线 v0.2.10 升级：prompt 改为「真人资深工程师」口吻（拆句+具体动词+项目落地叙事），含 few-shot 例。

- v8_raw → v8_rules+llm_v2：AI score 53 → 46（距 deepseek v9 标答仅差 6 分，旧版差 9 分）
- 字符数 1620 → 1723（开始补项目落地叙事，距 v9 的 2481 仍差 800 字展开深度）
- minimax-M3 thinking 极贪心，max_tokens 必须 ≥ 8000；max_chunk_chars 默认 1500
- base_url 走 `https://api.minimaxi.com/v1`，Authorization Bearer（X-Api-Key 会 401）

---

## [0.2.9] - 2026-09-28

LLM 兜底管线 + 专业度评分 + p05/p10 误报修复。