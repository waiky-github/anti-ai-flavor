# anti-ai-flavor

中文去 AI 味工具。40 个 pattern 规则 + 词库替换 + 场景感知判定，既能改写文本，也能当发布前的强制校验闸门。

## 安装

```bash
pip install anti-ai-flavor
```

## 快速开始

```python
from anti_ai_flavor import rewrite_text, detect_all

text = "这项目不仅提升了效率，也增强了用户体验。"
clean = rewrite_text(text)
print(clean)

result = detect_all(text)
print(result)
```

## CLI

```bash
# 重写文本（纯规则，LLM 默认关闭）
anti-ai-flavor rewrite input.md -o output.md

# 显式启用 LLM 后处理改写
anti-ai-flavor rewrite input.md --llm -o output.md

# 输出评分报告（JSON）
anti-ai-flavor rewrite input.md --report

# 检测并清理水印/异常字符
anti-ai-flavor rewrite input.md --watermark

# 指定 LLM 模型和 base URL
anti-ai-flavor rewrite input.md --llm --llm-model gpt-4o --llm-base-url https://api.openai.com/v1

# 从 stdin 读取
cat input.md | anti-ai-flavor rewrite

# 检测密度（是否还残留 AI 套话）
anti-ai-flavor density input.md

# 批量检查目录下所有 markdown
anti-ai-flavor check-docs ./docs

# LLM 检测（只读，不改写，默认关闭）
anti-ai-flavor detect input.md
```

## 设计

### 四层结构

1. 检测层：40 个 pattern + legacy 词库，只负责「有没有 AI 味」，不判处置。
2. 判定层：场景 profile 决定同一处命中该扣多少分、哪些算合规红线。
3. 处置层：按分数带给出 pass / warn / rewrite / block 四档动作。
4. 改写层：规则改写 + 场景化 LLM prompt 增量，失败一律回退原文。

pattern 分档：

- P1-P4：强 pattern，直接修复（not X but Y、one-line closer、staged run-up、arguing with no one）
- P5：只标记不修改
- P6-P10：高优先级（过度谨慎、虚假失衡、meta-commentary、虚假权威、列表疲劳）
- P11-P16：中优先级（反问、过渡词、被动语态、名词化、抽象主语、套话结尾）
- P17-P25：低优先级（强制正式、排比节奏、过度限定、生硬衔接、冗余说明、过度结构化、虚假精确、道德化、故意模糊）
- P26-P40：叙事与合规层（身体反应、金句、分阶段坦白、假身份、模板枚举、对比否定、破折号滥用、医疗功效、绝对化用语、替代医生、空洞升华、三段排比、营销话术）

### 场景

`--scene auto`（默认）先用语域特征识别场景，再用该场景的口径判定：

| 场景 | 语域特征 | 判定带（warn/rewrite/block） | 额外 |
| --- | --- | --- | --- |
| `social-note` | 小红书 / 笔记 / 收藏 / 评论区 / 毛孩子 | 85 / 68 / 50 | p27 口语化不扣分，p32、p40 计入 |
| `health-content` | 猫狗 / 兽医 / 癣 / 疫苗 / 铲屎官 | 90 / 75 / 65 | p35 医疗功效、p37 替代医生算合规红线，跨场景也拦 |
| `tech-doc` | git / 部署 / 报错 / 函数 / 回滚 | 85 / 70 / 55 | 允许必要枚举与命令 |
| `base` | 兜底 | 85 / 70 / 55 | 只覆盖任何场景都不该出现的表达 |

合规红线命中时无视分数直接 block：改写掩盖不了字面问题，工具不该替用户背这口锅。

### 动作分档

- pass：分数 ≥ warn_at，放行
- warn：rewrite_at ≤ 分数 < warn_at，可用但会提示
- rewrite：block_at < 分数 < rewrite_at，改写后仍建议人工复核
- block：分数 ≤ block_at 或命中合规红线，不改写、原样输出

### 空白保真

改写过程用私用区哨兵保护段落分隔与段内断行，出口原样还原；100 分文本改写必须逐字幂等。发布前闸门要的是「不该改的一个字都不改」。

## 发布前闸门

`--gate` 才启用退出码分档，适合挂 CI 或发布脚本：

```bash
anti-ai-flavor rewrite note.md --scene auto --gate
echo $?   # 0=pass 或已改写可发；1=warn 有风险表达；2=block 不许发
```

gate 模式命中 block 时**不输出改写**，只报分数与命中项，退出码 2。不带 `--gate` 时保持旧行为：输出改写、退出码 0。

库 API 的 `scene="auto"` 会真跑场景识别，不会静默回落 base：

```python
from anti_ai_flavor import score_text

r = score_text(text, scene="auto")
print(r.scene, r.score, r.action, r.compliance_hit)
```

旧的白名单保守模式仍保留，但默认关闭（`rewrite_text(text, whitelist_strict=True)` 可恢复「仅 golden_set.json 精确匹配才改写」的行为）。

## 测试

```bash
pytest tests/ -v
```

## License

MIT

---

## 📮 关注我们

**公众号：AI Aperture** —— 分享 AI 工程实践、多 Agent 系统与开源项目经验。

![AI Aperture 公众号二维码](assets/ai-aperture-qr.jpg)

扫码关注，获取项目更新与更多技术内容。
