# Changelog

All notable changes to anti-ai-flavor are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

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