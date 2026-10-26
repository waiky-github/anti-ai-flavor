"""
profiles/scenes.py — 三个场景 profile（只写 delta）

| 场景            | 语域判断要点                                   |
|-----------------|------------------------------------------------|
| social-note     | 小红书/公众号等表达类内容；口语是正常语域，       |
|                 | 但网络烂梗、金句体、模板枚举仍是 AI 味            |
| health-content  | 宠物/医疗健康内容；合规红线优先于文风             |
| tech-doc        | 工程文档、提交信息、issue；枚举与量化是正常写法    |

每个 profile 只写相对底座的差异（罚分覆盖 / 停用 / 场景专属 / 合规），
通用指纹全部留在 profiles/base.py —— 避免同一条规则在多份配置里漂移。
"""

from __future__ import annotations

from .schema import ActionPolicy, SceneMarkers, SceneProfile


# --------------------------------------------------------------------------
# social-note：表达类内容（小红书笔记 / 公众号 / 博客）
# --------------------------------------------------------------------------
SOCIAL_NOTE = SceneProfile(
    name="social-note",
    label="表达类内容",
    description=(
        "面向读者的表达型内容，语域偏口语、允许语气词与第一人称。"
        "口语本身不是 AI 味，但网络烂梗堆砌、金句收尾、"
        "「三件事」式模板枚举、表演式坦诚，仍是 AI 痕迹。"
    ),
    aliases=("social_note", "socialnote", "creative_doc", "note", "xiaohongshu"),
    penalty_overrides={
        # 口语轻信号在本场景是正常语域：1 → 0（硬信号仍按底座罚）
        "p27_over_colloquial": 0,
        # 表达类内容里身体反应 + 格言金句是最典型的 AI 味，加重
        "p28_body_reaction": 4,
        "p29_maxim_golden_line": 4,
        "p30_staged_candor": 3,
        # 小红书满屏「三件事」式枚举，加重
        "p32_template_enumeration": 3,
    },
    disabled_patterns=(),
    # 2026-10-26 补 p40：场景专属 pattern 必须在这里显式登记才生效
    # （activate_patterns 只认 extra_patterns，pattern 自身 scenes 是第二道校验）
    extra_patterns=("p32_template_enumeration", "p40_marketing_hype"),
    compliance_patterns=(),
    policy=ActionPolicy(warn_at=85, rewrite_at=68, block_at=50),
    markers=SceneMarkers(
        strong=(
            "小红书", "笔记", "点赞", "收藏", "评论区", "粉丝", "发笔记",
            "姐妹们", "家人们", "宝妈", "宠物", "毛孩子", "萌宠",
        ),
        weak=(
            "今天", "真的", "居然", "第一次", "分享", "记录", "打卡",
            "哈哈", "～", "！", "#",
        ),
        min_score=3,
    ),
    notes="口语是正常语域，AI 味判据集中在「金句体 + 模板枚举 + 表演式坦诚」。",
)


# --------------------------------------------------------------------------
# health-content：宠物 / 医疗健康内容
# --------------------------------------------------------------------------
HEALTH_CONTENT = SceneProfile(
    name="health-content",
    label="健康内容",
    description=(
        "宠物健康、医疗、护理相关内容。合规红线优先于文风："
        "疗效宣称、替代就医、与医生对比一律拒绝发布，"
        "且**不做自动改写**——法律声明不能由工具代写。"
    ),
    aliases=("health_content", "health", "medical", "pet-health", "pet_health"),
    penalty_overrides={
        # 广告法在健康语境更严
        "p36_absolute_claim": 8,
        # 健康内容里的格言金句/身体反应修辞会削弱专业可信度
        "p29_maxim_golden_line": 4,
        "p28_body_reaction": 4,
    },
    disabled_patterns=(),
    extra_patterns=("p32_template_enumeration", "p35_medical_claim", "p37_replace_doctor",
                    "p40_marketing_hype"),
    compliance_patterns=("p35_medical_claim", "p37_replace_doctor"),
    # 领域闸门：只有文本确实在讲宠物/健康时，这两条合规则才跨场景生效。
    domain_markers=(
        "猫", "狗", "宠物", "毛孩子", "铲屎官", "喵", "汪",
        "兽医", "癣", "螨", "疫苗", "驱虫", "便便", "掉毛",
        # 2026-10-26 补（验收实测漏检）：「有了它就不用去医院了，在家自己判断就行」
        # 这条在 social-note 下没有宠物词，领域闸门直接跳过 p37。而「医院/医生/
        # 就诊」这类词技术文档不会出现，加进来不会误杀技术文（已用
        # 「根治线上抖动」技术样本回归验证过）。
        "医院", "医生", "就诊", "看病", "挂号", "症状",
    ),
    policy=ActionPolicy(warn_at=90, rewrite_at=75, block_at=65),
    markers=SceneMarkers(
        strong=(
            "医院", "医生", "兽医", "诊断", "症状", "用药", "处方",
            "复查", "筛查", "猫癣", "猫藓", "肠胃", "疫苗", "驱虫",
        ),
        weak=(
            "宠物", "猫", "狗", "主人", "毛孩子", "喂", "吃",
            "护理", "便便", "呕吐", "掉毛",
        ),
        min_score=4,
    ),
    notes=(
        "健康合规命中 → 直接 block，禁止自动改写；"
        "文风类问题仍可 rewrite。"
    ),
)


# --------------------------------------------------------------------------
# tech-doc：工程文档 / 提交信息 / issue 回复
# --------------------------------------------------------------------------
TECH_DOC = SceneProfile(
    name="tech-doc",
    label="工程文档",
    description=(
        "代码提交信息、issue/PR 回复、运维排障记录、技术方案。"
        "枚举、量化指标、被动语态在这里是正常写法，"
        "AI 味判据集中在空洞抽象词、假权威、模板化过渡。"
    ),
    aliases=(
        "tech_doc", "techdoc", "code", "coder",
        "coder_commit", "coder_issue_reply", "coder_pr",
        "ops_troubleshoot", "ops_log",
    ),
    penalty_overrides={
        # 技术文档列「三个维度」「四个阶段」是正常结构（p32 也不在 tech-doc 生效）
        # 第一人称叙事/身体反应在技术文档里不该出现，但也不算 AI 味主力
        "p28_body_reaction": 2,
        "p29_maxim_golden_line": 2,
        "p31_rhetorical_identity": 2,
    },
    disabled_patterns=(),
    extra_patterns=(),
    compliance_patterns=(),
    policy=ActionPolicy(warn_at=85, rewrite_at=70, block_at=55),
    markers=SceneMarkers(
        strong=(
            "git", "commit", "issue", "pull request", "CI", "部署",
            "日志", "报错", "接口", "函数", "版本", "回滚",
            "docker", "kubernetes", "pytest", "traceback",
        ),
        weak=(
            "配置", "参数", "测试", "构建", "依赖", "分支", "合并",
            "服务", "进程", "端口", "报错", "修复",
        ),
        min_score=4,
    ),
    notes="枚举与量化在工程语境正常，判据集中在空洞词与假权威。",
)


__all__ = ["SOCIAL_NOTE", "HEALTH_CONTENT", "TECH_DOC"]
