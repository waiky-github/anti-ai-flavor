"""
patterns/tier1_legacy.py — 现有 Tier 1 词表（向后兼容）

这些词表会被新的 25-pattern 体系调用，
也可以作为 fallback 直接使用。
"""

# === 中文 Tier 1 词 ===
# v0.2.12 (2026-09-30): 移除「链路」「机制」两项。
# 这两个词在工程/产品语境中是正常术语（如"链路追踪""缓存机制""告警机制""调用链路"），
# 真人技术文本被扣分 5 × 命中数；改由密度判定（density/红海词组合）兜底，
# 而不是单字命中即扣。模式暂留：因 AI 文本「业务模式/营销模式」空洞搭配多。
#
# v0.2.14 (2026-09-30): 继续移除「驱动」「体系」「支撑」「模式」四项。
# 这四个词在工程语境下同样是常用术语（"事件驱动""监控告警体系""后端支撑""Observer 模式"），
# 与 AI 味儿的"数据驱动方法推动""指标体系建设""业务支撑""业务模式"无法用规则区分。
# 跟"链路/机制"同一个逻辑：从 tier1_zh 移到 density/红海词组合兜底。
# 列表剩余 24 词全是「绝对不能写」的纯套话/AI 腔过渡词（首/综上所述/赋能/抓手/闭环/生态/格局/态势/基石/引擎/引领...），
# 这些词在工程语境中几乎不出现。
TIER1_ZH = [
    "当然", "首先", "值得注意的", "值得注意的是", "值得一提的是", "需要指出的是",
    "综上所述", "总而言之", "简而言之", "此外", "另外", "与此同时",
    "展示了", "反映了", "推动了",
    "赋能", "抓手", "闭环",
    "生态", "格局", "态势", "基石", "引擎",
    "引领",
]

# === 英文 Tier 1 词 ===
TIER1_EN = [
    "Absolutely!", "Moreover", "It's worth noting", "It is important to note",
    "Delve", "tapestry", "leverage", "seamless", "robust", "comprehensive",
    "game-changer", "serves as", "at its core", "In summary", "To sum up",
    "In conclusion", "To conclude",
]

# === 英文对称填充（跨句） ===
SYMMETRY_FILLERS_EN = [
    r"On one hand[\s\S]*?on the other hand[\s\S]*?[。.]",
    r"not only[^.]*but also[^.]*",
    r"both[^.]*and[^.]*",
]

# === 英文抽象主语 ===
ABSTRACT_SUBJECTS_EN = [
    r"The application of this technology[^.]*",
    r"This initiative helps[^.]*",
    r"On this basis[^,]*[,]",
    r"In a sense[^,]*[,]",
]

# === 英文固定衔接词 ===
FIXED_CONNECTORS_EN = [
    r"It is important to note that[^.]*",
    r"It should be emphasized that[^.]*",
    r"It is worth mentioning that[^.]*",
]

# === 英文总结性结尾 ===
SUMMARY_CLOSERS_EN = [
    r"In conclusion[^.]*",
    r"In summary[^.]*",
    r"To conclude[^.]*",
    r"Overall[^.]*",
    r"In the end[^.]*",
    r"Ultimately[^.]*",
]

# === 中文对称填充 ===
SYMMETRY_FILLERS = [
    r"一方面[^。]*另一方面[^。]*",
    r"既[^。]*又[^。]*",
    r"不仅[^。]*而且[^。]*",
    r"虽然[^。]*但[^。]*[^。]*",
]

# === 机械排序 ===
MECHANICAL_ORDERING = [
    r"首先[,，]",
    r"其次[,，]",
    r"最后[,，]",
    r"First[,.]",
    r"Second[,.]",
    r"Third[,.]",
    r"Finally[,.]",
]

# === 总结性结尾 ===
SUMMARY_CLOSERS = [
    r"综上所述",
    r"总而言之",
    r"简而言之",
    r"总的来说",
    r"由此可见",
    r"不难看出",
    r"具有重要意义",
]

# === 抽象主语 ===
ABSTRACT_SUBJECTS = [
    r"该技术的应用使得",
    r"这一举措有助于",
    r"在此基础上",
    r"从某种意义上说",
]

# === 成语 filler ===
IDIOM_FILLERS = [
    "与时俱进",
    "开拓创新",
    "砥砺前行",
    "不忘初心",
    "再接再厉",
]

# === 破折号过度使用 ===
EM_DASH_OVERUSE = r"——\s*——"

# === 冗余修饰词 ===
REDUNDANT_MODIFIERS = [
    # r"系统性的",  # 改为 cleanup 只删「的」后缀，保留「系统性」
    # r"全面的",    # 改为 cleanup 只删「的」后缀，保留「全面」
    # r"整体的?",  # 不删「整体」
    # r"整体",      # 保留，不删
    # r"多维度",    # 保留，不删
    r"深度的",
    r"全方位的",
    r"从而",
    r"进而",
    r"进一步",
    r"大力",
    r"积极",
    r"有效",
    r"明显",
    r"充分",
    # r"全面",      # 保留，不删
    # r"整体",      # 保留，不删
]

# === 密度填充（时代/趋势） ===
DENSITY_FILLERS = [
    r"在当今快速发展的时代[，,]",
    r"在当今时代[，,]",
    r"随着(?:社会|科技|经济|数字)的(?:快速)?发展[，,]",
    r"在(?:新|现代)形势下[，,]",
    r"在当前(?:国际|国内)形势下[，,]",
    r"势在必行",
]
