#!/usr/bin/env python3
"""第 4 阶段验收脚本 — 2026-10-26

不做单元测试能做的事，只跑「对抗性 + 真实语料」的三条量化验收：

  验收 1：对抗样本 ≥ 12/13 被判为不干净（raw 命中 ≥ 1）
  验收 2：负样本 10 条全部 raw = 0（不误杀正常文字）
  验收 3：同一篇小红书稿的 v3（AI 味重）分数 < v8（人写定稿）分数
  验收 4（本轮新增）：v3/v5/v8/v9 四版按 social-note 场景重算，分数单调上升

用法：PYTHONPATH=src .venv/bin/python scripts/acceptance_scene_2026_10_26.py
退出码 0 = 全过；1 = 有验收项未过。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anti_ai_flavor.scoring import score_text  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"

# ── 验收 1：13 条对抗样本（AI 味典型句式，含社媒语域） ───────────────
ADVERSARIAL = [
    ("金句收尾", "所以你看，养猫这件事从来不是技术问题，而是耐心问题。"),
    ("三段式排比", "它不只是掉毛，不只是皮屑，更是身体在向你发出求救信号。"),
    ("模板枚举", "第一，观察掉毛范围；第二，检查皮肤颜色；第三，及时就医。"),
    ("对偶否定", "不是所有的秃斑都可怕，也不是所有的掉毛都能等。"),
    ("破折号滥用",
     "那一刻我明白了——它不是在掉毛——它是在说话——它在求救。\n"
     "我坐在沙发上看了它很久——它趴着一动不动——我这才意识到——我错过了太多。"),
    ("医疗功效", "这款喷雾能根治猫癣，三天消炎，坚持用就不复发。"),
    ("替代医生", "有了它就不用去医院了，在家自己判断就行。"),
    ("绝对化", "这是目前最有效的猫咪皮肤自检方法，100% 准确。"),
    ("空洞升华", "这不仅仅是养宠，更是一种生活方式的全面升级。"),
    ("身体反应通胀", "那一刻我整个人都愣住了，手心发凉，眼泪差点掉下来。"),
    ("模板封面腔", "谁懂啊家人们！这个神器的出现，直接让养宠幸福感拉满！"),
    ("先抑后扬话术", "说实话我一开始也不信，用了之后才发现是真的香。"),
    ("亲历但抽象", "经历过这次我成长了很多，也想把这些经验分享给大家。"),
]

# ── 验收 2：10 条负样本（正常人话，不该被扣分） ────────────────────
NEGATIVE = [
    "猫背上秃了一块。我拍照传给小程序，它提示建议就诊。",
    "今天给它换了猫砂，它闻了半天才进去，进去了又出来。",
    "医院照了灯，说是猫藓。药膏一天抹两次，抹了快一个月。",
    "检查加药几百块，医保不报。心里骂了一句，还是交了。",
    "它不吃不喝两天，我第三个晚上才带去医院的。",
    "我把照片前后对比了一下，发现边缘其实没变大。",
    "医生说别自己涂药，涂错了会更麻烦。",
    "猫不舒服不会叫，只能靠你多看一眼。",
    "换季这波是猫藓高发期，温差大，猫又在换毛。",
    "微信搜全名就能找到，真遇上不至于抓瞎。",
]


def _ids(result) -> list[str]:
    """命中的 pattern id；跨场景合规命中不在 hits 里，单独补标。"""
    ids = [h.pattern_id or h.category for h in result.hits]
    cross = result.details.get("compliance_cross_scene") if result.details else None
    if cross:
        ids += [f"{pid}(跨场景合规)" for pid in cross]
    return ids


def check_adversarial() -> tuple[bool, str]:
    missed = []
    for name, text in ADVERSARIAL:
        result = score_text(text, scene="social-note")
        # 判为「不干净」= 有罚分 或 命中合规红线。只看 raw 会把 p35/p37
        # 这类跨场景合规命中误报成漏检（罚分由策略层接管，不进 raw）。
        if result.raw == 0 and not result.compliance_hit:
            missed.append(f"{name}（{result.score} 分，0 命中）")
    ok = len(missed) <= 1
    detail = f"命中 {len(ADVERSARIAL) - len(missed)}/{len(ADVERSARIAL)}"
    if missed:
        detail += "；漏检：" + "、".join(missed)
    return ok, detail


def check_negative() -> tuple[bool, str]:
    dirty = []
    for text in NEGATIVE:
        result = score_text(text, scene="social-note")
        if result.raw > 0 or result.compliance_hit:
            dirty.append(
                f"「{text[:14]}…」{result.score} 分（-{result.raw}），命中 {_ids(result)}"
            )
    ok = not dirty
    detail = f"干净 {len(NEGATIVE) - len(dirty)}/{len(NEGATIVE)}"
    if dirty:
        detail += "；误杀：" + "；".join(dirty)
    return ok, detail


def _fixture_score(name: str) -> tuple[int, int]:
    path = FIXTURES / name
    text = path.read_text(encoding="utf-8")
    result = score_text(text, scene="social-note")
    return result.score, result.raw


def check_versions() -> tuple[bool, str]:
    scores = {}
    for name in ("promo_07_v3.txt", "promo_07_v5.txt", "promo_07_v8.txt", "promo_07_v9.txt"):
        try:
            scores[name] = _fixture_score(name)
        except FileNotFoundError:
            continue
    if "promo_07_v3.txt" not in scores or "promo_07_v8.txt" not in scores:
        return False, "缺 v3/v8 语料，无法比对"
    v3 = scores["promo_07_v3.txt"][0]
    v8 = scores["promo_07_v8.txt"][0]
    monotonic = all(
        scores[a][0] <= scores[b][0]
        for a, b in zip(
            ["promo_07_v3.txt", "promo_07_v5.txt", "promo_07_v8.txt", "promo_07_v9.txt"],
            ["promo_07_v5.txt", "promo_07_v8.txt", "promo_07_v9.txt"],
        )
        if a in scores and b in scores
    )
    serial = " → ".join(f"{k.replace('promo_07_', '').replace('.txt', '')}:{v[0]}分/{v[1]}命中"
                        for k, v in scores.items())
    ok = v3 < v8 and monotonic
    return ok, f"{serial}（v3<v8: {v3 < v8}；单调: {monotonic}）"


def main() -> int:
    results = [
        ("验收1 对抗样本命中 ≥12/13", check_adversarial()),
        ("验收2 负样本全部零命中", check_negative()),
        ("验收3 版本分数 v3 < v8 且单调", check_versions()),
    ]
    failed = 0
    for label, (ok, detail) in results:
        mark = "✅" if ok else "❌"
        print(f"{mark} {label}：{detail}")
        if not ok:
            failed += 1
    print()
    print("全部通过" if failed == 0 else f"{failed} 项未过")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
