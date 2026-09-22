# anti-ai-flavor

中文去 AI 味工具。通过 25 个 pattern 规则 + 词库替换，降低文本的 AI 生成痕迹。

## 安装

```bash
pip install anti-ai-flavor
```

## 快速开始

```python
from anti_ai_flavor import rewrite_text, detect_all

text = "这个方案提升了效率，也增强了稳定性。"
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

25 个 pattern 分 4 档优先级：

- P1-P4：强 pattern，直接修复（not X but Y、one-line closer、staged run-up、arguing with no one）
- P5：只标记不修改
- P6-P10：高优先级（过度谨慎、虚假失衡、meta-commentary、虚假权威、列表疲劳）
- P11-P16：中优先级（反问、过渡词、被动语态、名词化、抽象主语、套话结尾）
- P17-P25：低优先级（强制正式、排比节奏、过度限定、生硬衔接、冗余说明、过度结构化、虚假精确、道德化、故意模糊）

补充 legacy 规则：Tier 1/2/3 词库、机械排序、对称填充、总结结尾、抽象主语、密度填充、成语 filler。

## 测试

```bash
pytest tests/ -v
```

## License

MIT
