#!/usr/bin/env python3
"""anti_ai_flavor/professionalism.py — 专业度评分维度

2026-09-28 新增。5 个独立维度，每个 0-100 分：

1. specificity（具体度）：抽象词少、具体词多 = 具体度高
2. detail_density（细节密度）：数字/日期/专有名词密度
3. sentence_variance（句长方差）：句长差异大 = 像真人；AI 句长方差小
4. professional_terms（专业术语密度）：长词比例
5. complexity（句法复杂度）：逗号/句号比衡量从属结构

对比 deepseek / writing-humanizer 类工具的核心差距：
- 我们之前只扣 AI 味分（负向）
- 现在补上"专业度"（正向）——真实好文本应该同时低 AI 味 + 高专业度

调用：
    from anti_ai_flavor.professionalism import compute_professionalism
    result = compute_professionalism(text)
    print(result.score, result.dimensions)
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ============================================================
# 1. 具体度（specificity）
# ============================================================

# 抽象词（AI 喜欢用）—— AI 文本里这些词比例高
ABSTRACT_WORDS = {
    # 中文抽象名词/形容词
    "方面", "层面", "角度", "维度", "视角", "方向", "领域", "范围", "模式",
    "形式", "方式", "方法", "策略", "路径", "方案", "机制", "体系", "系统",
    "架构", "框架", "平台", "生态", "闭环", "链路", "全链路", "全方位",
    "系统性", "全面性", "综合性", "整体性", "多维度", "多元化", "多层次",
    "可持续", "高质量发展", "协同", "赋能", "价值", "意义", "重要性",
    "优势", "劣势", "特色", "亮点", "创新", "变革", "转型", "升级",
    "优化", "提升", "改进", "增强", "扩大", "拓展", "延伸",
    # 英文抽象词
    "aspect", "dimension", "perspective", "framework", "architecture",
    "ecosystem", "holistic", "comprehensive", "systematic", "synergy",
    "leverage", "facilitate", "enhance", "optimize", "streamline",
    "robust", "scalable", "sustainable", "transformative", "paradigm",
}

# 具体词（真人/专业文会有的）—— 数字/日期/人名/地名/单位
SPECIFIC_PATTERNS_ZH = [
    (r"\d{4}年\d{1,2}月\d{1,2}日", "date"),         # 日期
    (r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", "date"),       # 日期
    (r"\d+\.\d+", "decimal"),                       # 小数
    (r"\d+%", "percent"),                            # 百分比
    (r"\d+\s*[万亿千百]", "chinese_unit"),          # 万/亿
    (r"[A-Z]{2,}", "acronym"),                       # 英文缩写
    (r"[A-Z][a-z]+(?:[A-Z][a-z]+)+", "camel_case"),  # 驼峰命名
    (r"\d+(?:GB|MB|KB|Hz|MHz|GHz|ms|s)", "tech_unit"),  # 技术单位
    (r"v\d+\.\d+", "version"),                        # 版本号
]

# 停用词（不计入具体度判定）
STOPWORDS_ZH = set("的了是在和与及或也都很就才都还但是然而因此所以".split())


def compute_specificity(text: str) -> Tuple[int, Dict[str, float]]:
    """
    计算具体度（0-100）：
    - 抽象词密度越低越好
    - 具体词（数字/日期/专名）密度越高越好
    """
    if not text.strip():
        return 50, {"abstract_density": 0.0, "specific_density": 0.0}

    chars = len(re.sub(r"\s", "", text))

    # 抽象词命中次数（按字符切分）
    abstract_count = 0
    for word in ABSTRACT_WORDS:
        abstract_count += text.count(word)

    # 具体模式命中次数
    specific_count = 0
    for pattern, _ in SPECIFIC_PATTERNS_ZH:
        specific_count += len(re.findall(pattern, text))

    abstract_density = abstract_count / max(chars / 100, 1)  # 每 100 字符
    specific_density = specific_count / max(chars / 100, 1)

    # 线性映射：abstract_density < 2 给 100，> 8 给 0
    abstract_score = max(0, min(100, int(100 - (abstract_density - 2) * 12.5)))

    # specific_density > 5 给 100，< 1 给 0
    specific_score = max(0, min(100, int((specific_density - 0.5) * 22)))

    # 加权平均（abstract 占 40%，specific 占 60%——专业文具体度更重要）
    score = int(abstract_score * 0.4 + specific_score * 0.6)

    return score, {
        "abstract_density": round(abstract_density, 2),
        "specific_density": round(specific_density, 2),
    }


# ============================================================
# 2. 细节密度（detail_density）
# ============================================================

def compute_detail_density(text: str) -> Tuple[int, Dict[str, float]]:
    """
    细节密度（0-100）：
    - 数字 + 日期 + 专有名词密度
    - 真人写作会给具体数字，AI 喜欢用「大量」「若干」
    """
    if not text.strip():
        return 50, {"detail_count": 0, "char_count": 0}

    detail_count = 0
    for pattern, _ in SPECIFIC_PATTERNS_ZH:
        detail_count += len(re.findall(pattern, text))

    chars = len(re.sub(r"\s", "", text))

    # 每 100 字符的细节数
    density = detail_count / max(chars / 100, 1)

    # density >= 4 给 100，density <= 0.5 给 0
    score = max(0, min(100, int((density - 0.5) * 28.5)))

    return score, {"detail_count": detail_count, "char_count": chars}


# ============================================================
# 3. 句长方差（sentence_variance）
# ============================================================

def _split_sentences(text: str) -> List[str]:
    """分句（按中英文标点）。"""
    parts = re.split(r"[。！？!?；;\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def compute_sentence_variance(text: str) -> Tuple[int, Dict[str, float]]:
    """
    句长方差（0-100）：
    - 真人写作句长差异大
    - AI 写作句长方差小（每句差不多长）
    - 但技术文档/简历句长本来方差就小，不能因为"句长均匀"就扣分
    - 改用相对判断：CV < 0.1 = 极端 AI 风格扣分；CV > 0.5 = 真人风格加分
    """
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return 50, {"mean_length": 0.0, "stdev_length": 0.0, "cv": 0.0}

    lengths = [len(re.sub(r"\s", "", s)) for s in sentences]
    mean_len = statistics.mean(lengths)
    stdev_len = statistics.stdev(lengths) if len(lengths) >= 2 else 0.0

    # 变异系数 CV = stdev / mean
    cv = stdev_len / mean_len if mean_len > 0 else 0.0

    # 阈值（更宽容，因为技术文档 CV 普遍小）：
    # CV <= 0.08 → AI 风格扣分（30）
    # CV >= 0.50 → 真人风格加分（100）
    # 0.08 ~ 0.50 之间线性
    if cv <= 0.08:
        score = 30
    elif cv >= 0.50:
        score = 100
    else:
        score = int(30 + (cv - 0.08) / (0.50 - 0.08) * 70)

    return score, {
        "mean_length": round(mean_len, 2),
        "stdev_length": round(stdev_len, 2),
        "cv": round(cv, 3),
    }


# ============================================================
# 4. 专业术语密度（professional_terms）
# ============================================================

# 中文常见停用词（不计入专业术语）
CN_STOPWORDS = set("""
的了是在和与及或也都很就才都还但是然而因此所以我们你们他们她们它们这个那个这些那些
什么怎么为什么哪里哪个多少几谁怎么样的啊呢吗吧嗯哦哈唉嘛呀啦哟啊哦哈
""")


def _split_chinese_words(text: str) -> List[str]:
    """
    简易中文分词：基于标点和停用词切分。
    （不引入 jieba 依赖，保持 zero-dep）
    """
    # 先按标点切
    parts = re.split(r"[，。！？；：、\s,.;:!?\n]+", text)
    words = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 简易切分：找连续中文 2-6 字 + 非停用词的片段
        # 用一个简单规则：扫描，连续的非停用字累计到 2-6 字就形成一个词
        i = 0
        n = len(part)
        while i < n:
            c = part[i]
            if c in CN_STOPWORDS or not ('\u4e00' <= c <= '\u9fff'):
                i += 1
                continue
            # 从 i 开始，找最长非停用字串
            j = i
            while j < n and part[j] not in CN_STOPWORDS and ('\u4e00' <= part[j] <= '\u9fff'):
                j += 1
            word = part[i:j]
            if 2 <= len(word) <= 6:
                words.append(word)
            i = j
    return words


def compute_professional_terms(text: str) -> Tuple[int, Dict[str, float]]:
    """
    专业术语密度（0-100）：
    - 长词（4-6 字）比例高 = 专业
    - 但要避免"系统性""全面性"等抽象 filler——这些不计入专业术语
    """
    if not text.strip():
        return 50, {"long_word_ratio": 0.0, "abstract_filler_ratio": 0.0}

    words = _split_chinese_words(text)
    if not words:
        return 50, {"long_word_ratio": 0.0, "abstract_filler_ratio": 0.0}

    long_words = [w for w in words if len(w) >= 4]
    abstract_fillers = [w for w in long_words if w in ABSTRACT_WORDS]

    long_word_ratio = len(long_words) / len(words)
    abstract_filler_ratio = (
        len(abstract_fillers) / len(long_words) if long_words else 0.0
    )

    # 有效长词 = 长词 - 抽象 filler
    effective_ratio = long_word_ratio * (1 - abstract_filler_ratio)

    # effective_ratio >= 0.5 给 100，<= 0.1 给 0
    score = max(0, min(100, int((effective_ratio - 0.1) * 250)))

    return score, {
        "long_word_ratio": round(long_word_ratio, 3),
        "abstract_filler_ratio": round(abstract_filler_ratio, 3),
    }


# ============================================================
# 5. 句法复杂度（complexity）
# ============================================================

def compute_complexity(text: str) -> Tuple[int, Dict[str, float]]:
    """
    句法复杂度（0-100）：
    - 句内逗号数 / 句数 = 平均每句从属/并列结构
    - AI 文本常常 3-4 个并列短语；真人变化大
    - 阈值：1.5-2.5 为佳，过低（孤立短句堆砌）或过高（极端并列）扣分
    """
    sentences = _split_sentences(text)
    if not sentences:
        return 50, {"avg_clauses_per_sentence": 0.0}

    # 计算每句的逗号数（从属结构代理）
    comma_counts = [s.count("，") + s.count(",") for s in sentences]
    avg_clauses = statistics.mean(comma_counts) if comma_counts else 0.0

    # 目标区间 [1.0, 2.5]，峰值在 1.5-2.0
    if avg_clauses < 0.5:
        score = int(40 + avg_clauses * 40)  # 太简单 0.5 → 60
    elif avg_clauses <= 2.0:
        score = 100  # 理想区间
    elif avg_clauses <= 3.5:
        score = int(100 - (avg_clauses - 2.0) * 26.6)  # 2.0 → 100, 3.5 → 60
    else:
        score = max(0, int(60 - (avg_clauses - 3.5) * 15))  # > 3.5 扣分

    return score, {"avg_clauses_per_sentence": round(avg_clauses, 2)}


# ============================================================
# 综合：专业度评分
# ============================================================

@dataclass
class ProfessionalismResult:
    score: int                                  # 0-100 综合分
    dimensions: Dict[str, int] = field(default_factory=dict)
    details: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "score": self.score,
            "dimensions": self.dimensions,
            "details": self.details,
        }


# 各维度权重
WEIGHTS = {
    "specificity": 0.25,
    "detail_density": 0.25,
    "sentence_variance": 0.15,
    "professional_terms": 0.20,
    "complexity": 0.15,
}


def compute_professionalism(text: str) -> ProfessionalismResult:
    """
    综合专业度评分（0-100）。

    5 个维度的加权平均。
    """
    spec_score, spec_details = compute_specificity(text)
    det_score, det_details = compute_detail_density(text)
    var_score, var_details = compute_sentence_variance(text)
    prof_score, prof_details = compute_professional_terms(text)
    cmp_score, cmp_details = compute_complexity(text)

    dimensions = {
        "specificity": spec_score,
        "detail_density": det_score,
        "sentence_variance": var_score,
        "professional_terms": prof_score,
        "complexity": cmp_score,
    }
    details = {
        "specificity": spec_details,
        "detail_density": det_details,
        "sentence_variance": var_details,
        "professional_terms": prof_details,
        "complexity": cmp_details,
    }

    overall = sum(
        dimensions[name] * WEIGHTS[name] for name in WEIGHTS
    )

    return ProfessionalismResult(
        score=int(overall),
        dimensions=dimensions,
        details=details,
    )


if __name__ == "__main__":
    # 简单测试
    test_text = """
    系统延迟从 230ms 降到 47ms，内存占用从 4.2GB 降到 1.8GB，启动速度从 8.3s 提升到 2.1s。
    我们用 vLLM 部署了 Qwen2.5-72B-Instruct 模型（FP8 量化），吞吐量达到 1280 tokens/s。
    2026 年 8 月上线后，故障恢复时间（MTTR）从 25 分钟缩短到 4 分钟。
    """
    result = compute_professionalism(test_text)
    print(f"综合分: {result.score}")
    print(f"维度: {result.dimensions}")
    print(f"细节: {result.details}")

    print()
    ai_text = """
    首先，值得注意的是，这个方案不仅提升了效率，而且增强了体验，更重要的是构建了系统性的闭环，
    实现了全方位的覆盖，打造了高质量发展的新格局。
    """
    ai_result = compute_professionalism(ai_text)
    print(f"AI 文本综合分: {ai_result.score}")
    print(f"AI 文本维度: {ai_result.dimensions}")
