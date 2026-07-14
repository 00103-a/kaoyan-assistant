import re
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any


def _normalize_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        text = str(value).strip()
    except Exception:
        return default
    return text if text else default


def _normalize_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    try:
        text = str(value).strip().lower()
    except Exception:
        return default
    if text in {"true", "1", "yes", "y", "是"}:
        return True
    if text in {"false", "0", "no", "n", "否"}:
        return False
    return default


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        raw_items = (
            value.replace("；", ",")
            .replace("，", ",")
            .replace("、", ",")
            .replace("\n", ",")
            .split(",")
        )
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]

    normalized = []
    for item in raw_items:
        text = _normalize_text(item)
        if text:
            normalized.append(text)
    return normalized


@dataclass
class KnowledgePointDraft:
    knowledge_name: str = ""
    knowledge_type: str = ""
    subject: str = ""
    chapter_name: str = ""
    core_definition: str = ""
    exam_question_styles: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    related_concepts: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    example_or_application: str = ""
    review_priority: str = "中"
    source_text: str = ""
    source_page: str = ""
    source_location: str = ""
    tags: list[str] = field(default_factory=list)
    mastery_state: str = "待复习"
    is_ai_expansion: bool = False
    uncertainty_note: str = ""


@dataclass
class ConfirmedKnowledgePoint:
    knowledge_name: str = ""
    knowledge_type: str = ""
    subject: str = ""
    chapter_name: str = ""
    core_definition: str = ""
    exam_question_styles: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    related_concepts: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    example_or_application: str = ""
    review_priority: str = "中"
    source_text: str = ""
    source_page: str = ""
    source_location: str = ""
    tags: list[str] = field(default_factory=list)
    mastery_state: str = "待复习"
    is_ai_expansion: bool = False
    uncertainty_note: str = ""


def _normalize_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        return dict(raw)
    except Exception:
        return {}


def _build_knowledge_payload(raw: Any) -> dict[str, Any]:
    payload = _normalize_payload(raw)
    return {
        "knowledge_name": _normalize_text(payload.get("knowledge_name"), "未命名知识点"),
        "knowledge_type": _normalize_text(payload.get("knowledge_type")),
        "subject": _normalize_text(payload.get("subject")),
        "chapter_name": _normalize_text(payload.get("chapter_name")),
        "core_definition": _normalize_text(payload.get("core_definition")),
        "exam_question_styles": _normalize_list(payload.get("exam_question_styles")),
        "keywords": _normalize_list(payload.get("keywords")),
        "related_concepts": _normalize_list(payload.get("related_concepts")),
        "pitfalls": _normalize_list(payload.get("pitfalls")),
        "example_or_application": _normalize_text(payload.get("example_or_application")),
        "review_priority": _normalize_text(payload.get("review_priority"), "中"),
        "source_text": _normalize_text(payload.get("source_text")),
        "source_page": _normalize_text(payload.get("source_page")),
        "source_location": _normalize_text(payload.get("source_location")),
        "tags": _normalize_list(payload.get("tags")),
        "mastery_state": _normalize_text(payload.get("mastery_state"), "待复习"),
        "is_ai_expansion": _normalize_bool(payload.get("is_ai_expansion"), False),
        "uncertainty_note": _normalize_text(payload.get("uncertainty_note")),
    }


def normalize_knowledge_point_draft(raw: dict) -> KnowledgePointDraft:
    try:
        return KnowledgePointDraft(**_build_knowledge_payload(raw))
    except Exception:
        return KnowledgePointDraft()


def normalize_knowledge_point_drafts(raw_items: list) -> list[KnowledgePointDraft]:
    if not isinstance(raw_items, list):
        return []

    normalized = []
    for item in raw_items:
        normalized.append(normalize_knowledge_point_draft(item))
    return normalized


def knowledge_point_to_dict(point: Any) -> dict:
    if is_dataclass(point):
        return asdict(point)

    if isinstance(point, dict):
        normalized = normalize_knowledge_point_draft(point)
        return asdict(normalized)

    try:
        payload = {}
        for item in fields(KnowledgePointDraft):
            payload[item.name] = getattr(point, item.name, None)
        return asdict(normalize_knowledge_point_draft(payload))
    except Exception:
        return asdict(KnowledgePointDraft())


def validate_required_fields(point: Any) -> list[str]:
    warnings = []
    payload = knowledge_point_to_dict(point)

    if not _normalize_text(payload.get("knowledge_name")) or payload.get("knowledge_name") == "未命名知识点":
        warnings.append("knowledge_name 缺失或为默认值")
    if not _normalize_text(payload.get("source_text")):
        warnings.append("source_text 为空，建议补充原文依据")
    if not _normalize_text(payload.get("core_definition")):
        warnings.append("core_definition 为空")

    return warnings


def has_meaningful_knowledge_content(point: Any) -> bool:
    """Return whether a draft represents a real knowledge point worth persisting."""
    payload = knowledge_point_to_dict(point)
    name = _normalize_text(payload.get("knowledge_name"))
    if not name or name == "未命名知识点":
        return False
    return bool(
        _normalize_text(payload.get("core_definition"))
        or _normalize_text(payload.get("source_text"))
    )


_PROMO_FRAGMENT_PATTERNS = (
    re.compile(r"更多计算机考研资料和信息[，,]?\s*请扫码咨询\s*>*", re.IGNORECASE),
    re.compile(r"(?:请|立即)?扫码(?:咨询|领取|添加)[^。；;\n]*", re.IGNORECASE),
    re.compile(r"王道计算机考研(?:团队)?", re.IGNORECASE),
    re.compile(r"(?:微信|QQ|qq群|公众号)[:：号\s]*[A-Za-z0-9_-]{4,}", re.IGNORECASE),
)
_PLACEHOLDER_NAME_RE = re.compile(r"^(?:候选)?知识点\s*\d*$")
_LEARNING_SIGNALS = (
    "学习", "复习", "备考", "心得", "经验", "感悟", "方法", "策略", "规划",
    "真题", "模拟", "刷题", "错题", "笔记", "考场", "时间分配", "跳题",
    "阶段", "教材", "网课", "建议", "择校", "代码题",
)
_CS408_SIGNALS = (
    "408", "数据结构", "计算机组成", "组成原理", "操作系统", "计算机网络",
    "算法", "树", "图", "栈", "队列", "CPU", "缓存", "页表", "TLB", "协议",
)
_PERSONAL_PROFILE_SIGNALS = (
    "个人背景", "关于作者", "本科", "报考院校", "初试成绩", "总分", "四级",
    "六级", "无科研", "无竞赛", "某二本", "某双非",
)
_PUBLICATION_NOISE_RE = re.compile(
    r"(?:出版社|\bPRESS\b|AGRICULTUREPRESS|编著|主编|学习包|书课|配合使用|"
    r"金榜时代|GLIST|全捞時代|金榜晴代|基础篇|数学[一二三1-3、，,\s]+通用|"
    r"配套练习|学习水平自测|高效掌握|做题事半功倍|复习全书|辅导讲义|"
    r"严选题|领跑计划|养成笔记)",
    re.IGNORECASE,
)
_MATH_SIGNALS = (
    "函数", "极限", "连续", "导数", "微分", "积分", "方程", "级数", "向量",
    "矩阵", "概率", "统计", "定理", "曲线", "曲面", "单调", "奇函数", "偶函数",
    "周期", "有界", "多元", "二重积分", "微分方程", "线性代数",
)


def _strip_promotional_fragments(value: Any) -> str:
    text = _normalize_text(value)
    for pattern in _PROMO_FRAGMENT_PATTERNS:
        text = pattern.sub(" ", text)
    for marker in ("数据结构", "计算机组成原理", "组成原理", "操作系统", "计算机网络"):
        marker_pattern = re.compile(rf"(?<!\S){re.escape(marker)}(?!\S)")
        if len(marker_pattern.findall(text)) >= 2:
            text = marker_pattern.sub(" ", text)
    text = re.sub(r"\s*题\d+[：:]\s*\d+\s*-?\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" >，,；;:：-")
    return text


def _infer_learning_entry_name(text: str) -> str:
    compact = _normalize_text(text)
    if "代码题" in compact and any(token in compact for token in ("暴力解", "最优解", "考场")):
        return "代码题考场策略"
    if "考场" in compact and any(token in compact for token in ("分钟", "时间", "跳过")):
        return "考场时间分配与跳题策略"
    if "择校" in compact:
        return "择校风险控制经验"
    if any(token in compact for token in ("第一轮", "第二轮", "三轮", "基础阶段", "强化阶段", "冲刺阶段")):
        return "复习阶段规划"
    if "模拟" in compact and "真题" in compact:
        return "真题与模拟训练安排"
    if "笔记" in compact:
        return "专业课笔记与复习方法"
    if "刷题" in compact or "错题" in compact:
        return "刷题与复盘方法"
    return ""


def prepare_knowledge_point_for_storage(point: Any, subject: str = "") -> tuple[dict, str]:
    """Sanitize and classify a reusable learning entry; return a rejection reason when irrelevant."""
    payload = knowledge_point_to_dict(point)
    original_text = " ".join(
        _normalize_text(payload.get(field))
        for field in ("knowledge_name", "core_definition", "source_text")
    )
    for field in ("knowledge_name", "core_definition", "source_text", "uncertainty_note"):
        payload[field] = _strip_promotional_fragments(payload.get(field))

    name = _normalize_text(payload.get("knowledge_name"))
    was_placeholder = bool(
        not name or name == "未命名知识点" or _PLACEHOLDER_NAME_RE.fullmatch(name)
    )
    combined = " ".join(
        _normalize_text(payload.get(field))
        for field in ("knowledge_name", "core_definition", "source_text")
    )
    if not name or name == "未命名知识点" or _PLACEHOLDER_NAME_RE.fullmatch(name):
        inferred_name = _infer_learning_entry_name(combined)
        if inferred_name:
            payload["knowledge_name"] = inferred_name
            name = inferred_name

    if not name or name == "未命名知识点" or _PLACEHOLDER_NAME_RE.fullmatch(name):
        return payload, "占位名称且无法识别有效主题"
    if not (_normalize_text(payload.get("core_definition")) or _normalize_text(payload.get("source_text"))):
        return payload, "没有定义、心得、经验或原文依据"

    learning_hits = sum(token in combined for token in _LEARNING_SIGNALS)
    personal_hits = sum(token in combined for token in _PERSONAL_PROFILE_SIGNALS)
    if "个人背景" in name or personal_hits >= 3:
        return payload, "个人履历或成绩信息，不属于可复用学习内容"
    if _PUBLICATION_NOISE_RE.search(name):
        return payload, "封面、书名、作者或出版信息，不属于学习条目"

    clean_subject = _normalize_text(subject or payload.get("subject"))
    if "408" in clean_subject:
        if any(token in name for token in ("考研数学", "数学复习", "政治复习", "英语复习", "线性代数")):
            return payload, "内容属于其他考试科目"
        cs_hits = sum(token.lower() in combined.lower() for token in _CS408_SIGNALS)
        other_subject_hits = sum(token in combined for token in ("数学一", "数一", "政治", "英语一", "英一"))
        if other_subject_hits and (was_placeholder or (not cs_hits and learning_hits < 2)):
            return payload, "内容与当前 408 学科无关"
    if clean_subject in {"数一", "数二", "数三"} or "数学" in clean_subject:
        math_hits = sum(token in combined for token in _MATH_SIGNALS)
        is_question = _normalize_text(payload.get("knowledge_type")) == "题目"
        if not math_hits and not is_question and learning_hits < 2:
            return payload, "内容与当前数学学科无关"

    sanitized_removed = len(re.sub(r"\s+", "", original_text)) - len(re.sub(r"\s+", "", combined))
    if sanitized_removed > 0 and len(re.sub(r"\s+", "", combined)) < 20:
        return payload, "仅包含广告、联系方式或引流内容"

    current_type = _normalize_text(payload.get("knowledge_type"))
    if current_type in {"题目", "章节提纲"}:
        payload["knowledge_type"] = current_type
    elif any(token in combined for token in ("心得", "感悟")):
        payload["knowledge_type"] = "学习心得"
    elif any(token in combined for token in ("备考", "考场", "真题", "模拟", "刷题", "择校")):
        payload["knowledge_type"] = "备考经验"
    elif any(token in combined for token in ("复习阶段", "规划", "方法", "策略", "笔记")):
        payload["knowledge_type"] = "方法/策略"
    elif not current_type:
        payload["knowledge_type"] = "专业知识"

    return payload, ""
