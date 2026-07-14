import json
import math
import re
from typing import Callable

from schemas.knowledge_schema import (
    has_meaningful_knowledge_content,
    knowledge_point_to_dict,
    normalize_knowledge_point_draft,
    normalize_knowledge_point_drafts,
    validate_required_fields,
)


def build_knowledge_json_prompt(
    text: str,
    subject: str = "",
    chapter_name: str = "",
    max_points: int = 12,
    extraction_guidance: str = "",
    outline_mode: bool = False,
) -> str:
    guidance = (extraction_guidance or "").strip()
    grounding_rule = "不能突破提纲所限定的学科范围" if outline_mode else "不能突破原文依据"
    guidance_block = (
        f"\n学科补充抽取规则（只用于强调重点，{grounding_rule}）：\n{guidance}\n"
        if guidance
        else ""
    )
    if outline_mode:
        opening = (
            "你是专业课知识点扩展助手。输入内容是从图片型 PDF 抽样识别出的目录/章节提纲，"
            "或从文字型考试大纲提取的原文层级提纲，不是完整教材原文。"
            "请以提纲限定范围，结合通用考研知识发散出可独立复习的知识点。"
        )
        source_rule = "source_text 必须逐字引用触发本知识点的提纲标题，不得伪造教材原文。"
        directory_rule = "目录/章节提纲正是本任务的有效依据；不要把页眉、页脚、广告和乱码当成知识点。"
        expansion_rules = (
            "\n21. 仅根据目录标题补全定义或考法时设置 is_ai_expansion=true，并在 uncertainty_note 标明“基于提纲AI发散，需核对教材”。"
            "\n22. 如果原文是题目，应设置 knowledge_type=\"题目\"，knowledge_name 概括考点，source_text 保留题干；原样整理题目时 is_ai_expansion=false。"
            "\n23. 不得把封面、书名、作者、出版社、课程宣传或题册广告保存为学习条目。"
            "\n24. AI 补全的定义、考法、易错点不得声称来自教材原文。"
        )
        material_label = "提纲原文"
    else:
        opening = (
            "你是专业课学习资料整理助手。请只基于用户提供的资料内容整理可复用的学习条目，"
            "不要编造资料中没有的事实。条目既可以是专业知识，也可以是与当前学科直接相关的学习心得、备考经验或方法策略。"
        )
        source_rule = "source_text 必须尽量引用原文片段作为依据。"
        directory_rule = "不要把页眉、页脚、目录项、参考文献、作者单位、普通过渡句、例题编号、纯说明性废话当成知识点。"
        expansion_rules = ""
        material_label = "资料原文"
    return f"""{opening}

任务要求：
1. 输出必须是合法 JSON 数组。
2. 不要输出 Markdown。
3. 不要输出 ```json。
4. 不要输出任何解释性文字。
5. 最多输出 {max_points} 个学习条目对象。
6. 每个对象尽量包含以下字段：
   - knowledge_name
   - knowledge_type
   - subject
   - chapter_name
   - core_definition
   - exam_question_styles
   - keywords
   - related_concepts
   - pitfalls
   - example_or_application
   - review_priority
   - source_text
   - source_page
   - source_location
   - tags
   - mastery_state
   - is_ai_expansion
   - uncertainty_note
7. {source_rule}
8. source_page 必须尽量从资料中的“=== 第N页 ===”标记中提取；无法判断时留空并写 uncertainty_note。
9. source_location 必须尽量填写题号、段落或小节，例如“题5”“题16”“数据结构题6”。
10. 允许提取两类内容：A. 可复习、可考察的专业概念、原理、算法、结构、协议、机制、公式、模型或典型考法；B. 与当前学科直接相关、可复用的学习心得、备考经验、复习方法、做题策略和时间规划。
11. {directory_rule}
12. 如果某字段无法从原文判断，可以留空，或写入 uncertainty_note。
13. 如果某项内容属于 AI 发散或补全，必须标记 is_ai_expansion=true。
14. exam_question_styles、keywords、related_concepts、pitfalls、tags 应尽量使用数组。
15. 为避免 JSON 过长，摘要类字段尽量控制在 160 字以内，source_text 尽量保留完整题干、定义句或上下文证据，建议 80-300 字。
16. knowledge_type 应按内容填写“专业知识”“题目”“章节提纲”“学习心得”“备考经验”或“方法/策略”，专业概念也可使用更具体的原理、算法、考法等类型。
17. 严禁保存广告、扫码咨询、联系方式、机构宣传、作者个人背景、院校报考履历、个人成绩、与当前学科无关的数学/政治/英语内容，以及“候选知识点1”之类占位项。
18. 如果有效经验与广告混在一起，只保留可复用经验，source_text 中也必须删除广告和个人隐私信息。
19. knowledge_name 必须概括具体主题，不能使用“候选知识点”“知识点1”“经验1”等空泛名称。
20. 不要输出代码大段、整段解析、长公式推导；只输出可复习的结构化摘要。{expansion_rules}

学科：{subject}
章节：{chapter_name}
{guidance_block}

{material_label}：
{text}"""


def build_syllabus_knowledge_index_prompt(
    catalog: str,
    subject: str = "",
    max_points: int = 48,
    extraction_guidance: str = "",
) -> str:
    """Build one whole-document prompt that selects syllabus knowledge-point leaves."""
    guidance = (extraction_guidance or "").strip()
    guidance_block = f"\n补充筛选重点：{guidance}\n" if guidance else ""
    return f"""你是考研专业课大纲整理助手。下面是同一份考试大纲的完整层级提纲；必须先通读全文、理解科目和章节关系，再统一筛选知识点。

任务：从整份大纲中选出适合形成复习目录的具体知识点，最多 {max_points} 条，并尽量覆盖各科目和主要章节。

筛选规则：
1. 优先选择 [三级] 条目；只有 [二级] 没有任何 [三级] 子项时，才能选择该 [二级] 条目。
2. 不得把 [科目]、[一级]、仍有子项的 [二级] 标题当成知识点。
3. 不补写定义、考法、易错点或教材内容；这些内容由用户之后点击“AI 发散当前条目”单独生成。
4. 合并同义或重复条目，避免把同一主题拆成多个支离破碎的名称。
5. 只能选择大纲原文中真实存在的条目，不得凭常识新增知识点。
6. 每个可选叶子条目前都有唯一编号。最终只输出所选编号组成的 JSON 字符串数组，不要输出知识点正文、Markdown或解释。
7. 尽量选满 {max_points} 条；编号不得重复，也不得输出目录中不存在的编号。
{guidance_block}
当前专业课：{subject}

完整大纲：
{catalog}"""


def _strip_code_fences(text: str) -> str:
    cleaned = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_first_json_array(text: str) -> str:
    start = text.find("[")
    if start == -1:
        return ""

    depth = 0
    in_string = False
    escape_next = False
    for index in range(start, len(text)):
        char = text[index]
        if escape_next:
            escape_next = False
            continue
        if char == "\\" and in_string:
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return ""


def _parse_complete_json_objects(text: str) -> list[dict]:
    """Best-effort recovery when the model starts an array but truncates before closing it."""
    objects = []
    start = -1
    depth = 0
    in_string = False
    escape_next = False

    for index, char in enumerate(text or ""):
        if escape_next:
            escape_next = False
            continue
        if char == "\\" and in_string:
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                fragment = text[start:index + 1]
                try:
                    payload = json.loads(fragment)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict):
                    objects.append(payload)
                start = -1
    return objects


def parse_knowledge_points_json(raw_output: str, max_points: int = 12):
    warnings = []
    cleaned = _strip_code_fences(raw_output)
    payload = None

    parse_candidates = []
    if cleaned:
        parse_candidates.append(cleaned)
    first_array = _extract_first_json_array(cleaned)
    if first_array and first_array not in parse_candidates:
        parse_candidates.append(first_array)

    for candidate in parse_candidates:
        try:
            payload = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue

    if payload is None:
        recovered_objects = _parse_complete_json_objects(cleaned)
        if recovered_objects:
            payload = recovered_objects
            warnings.append("模型返回的 JSON 不完整，已尽力恢复其中完整的知识点对象。")
        else:
            warnings.append("模型返回的内容不是可解析的 JSON。")
            if cleaned:
                warnings.append(f"原始输出片段：{cleaned[:200]}")
            return [], warnings

    if isinstance(payload, dict):
        if isinstance(payload.get("knowledge_points"), list):
            payload = payload.get("knowledge_points")
        else:
            warnings.append("JSON 顶层不是数组，且未找到 knowledge_points 字段。")
            return [], warnings

    if not isinstance(payload, list):
        warnings.append("解析后的 JSON 不是数组。")
        return [], warnings

    normalized = normalize_knowledge_point_drafts(payload[:max_points])
    empty_count = sum(not has_meaningful_knowledge_content(item) for item in normalized)
    normalized = [item for item in normalized if has_meaningful_knowledge_content(item)]
    if empty_count:
        warnings.append(f"已忽略 {empty_count} 条没有名称、定义或原文依据的空知识点。")
    draft_dicts = [knowledge_point_to_dict(item) for item in normalized]

    for index, draft in enumerate(draft_dicts, start=1):
        for warning in validate_required_fields(draft):
            warnings.append(f"第{index}条：{warning}")

    return normalized, warnings


_PAGE_MARKER_PATTERN = re.compile(r"===\s*第\s*(\d+)\s*页\s*===")
_QUESTION_SPLIT_PATTERN = re.compile(r"\n\s*(?=(?:题\s*)?\d+\s*[.．、:：])")


def _strip_noise_lines(text: str) -> str:
    noise_tokens = (
        "聚创考研",
        "juchuang",
        "找研讯",
        "找真题",
        "找辅导",
        "考研网",
        "扫描二维码",
        "微信公众号",
    )
    lines = []
    for line in re.split(r"\n+", text or ""):
        stripped = line.strip()
        if not stripped:
            continue
        if any(token.lower() in stripped.lower() for token in noise_tokens):
            continue
        if re.fullmatch(r"[-—_\s\d/]+", stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _iter_page_sections(text: str):
    current_page = ""
    chunks = _PAGE_MARKER_PATTERN.split(text or "")
    if len(chunks) == 1:
        yield "", text or ""
        return

    prefix = chunks[0]
    if prefix.strip():
        yield "", prefix

    for index in range(1, len(chunks), 2):
        current_page = chunks[index].strip()
        content = chunks[index + 1] if index + 1 < len(chunks) else ""
        yield current_page, content


def _split_source_blocks_with_pages(text: str, max_points: int) -> list[tuple[str, str]]:
    cleaned = re.sub(r"\r\n?", "\n", text or "").strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if not cleaned:
        return []

    blocks = []
    for page, section in _iter_page_sections(cleaned):
        section = _strip_noise_lines(section)
        if not section.strip():
            continue
        raw_blocks = [
            block.strip()
            for block in re.split(r"\n\s*\n|(?=\n?\s*\d+[.、]\s*)", section)
            if block.strip()
        ]
        if len(raw_blocks) < 2:
            raw_blocks = [block.strip() for block in re.split(r"(?<=[。！？；;])\s*", section) if block.strip()]

        buffer = ""
        for block in raw_blocks:
            compact = re.sub(r"\s+", " ", block).strip()
            if not compact:
                continue
            if len(compact) < 28 and not _looks_like_meaningful_short_block(compact):
                continue
            if len(compact) < 45 and buffer:
                buffer = f"{buffer} {compact}".strip()
                continue
            if buffer:
                blocks.append((buffer, page))
            buffer = compact
            if len(blocks) >= max_points:
                return blocks[:max_points]
        if buffer and len(blocks) < max_points:
            blocks.append((buffer, page))

    return blocks[:max_points]


def _split_text_for_llm(text: str, target_chars: int = 2400, hard_limit: int = 3200) -> list[str]:
    cleaned = re.sub(r"\r\n?", "\n", text or "").strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if not cleaned:
        return []

    page_pieces = []
    for page, section in _iter_page_sections(cleaned):
        for piece in _split_page_section(page, section, hard_limit=hard_limit):
            if piece.strip():
                page_pieces.append(piece.strip())

    if not page_pieces:
        return [cleaned[:hard_limit]]

    chunks = []
    current = ""
    for piece in page_pieces:
        if not current:
            current = piece
            continue
        candidate = f"{current}\n\n{piece}"
        if len(candidate) <= hard_limit:
            current = candidate
            continue
        chunks.append(current)
        current = piece

    if current:
        chunks.append(current)

    merged = []
    buffer = ""
    for chunk in chunks:
        if not buffer:
            buffer = chunk
            continue
        candidate = f"{buffer}\n\n{chunk}"
        if len(buffer) < target_chars and len(candidate) <= hard_limit:
            buffer = candidate
            continue
        merged.append(buffer)
        buffer = chunk
    if buffer:
        merged.append(buffer)

    return merged or [cleaned[:hard_limit]]


def _select_chunks_for_point_budget(chunks: list[str], max_points: int) -> list[tuple[int, str]]:
    """Select source chunks evenly when the point budget cannot cover every chunk."""
    if not chunks or max_points <= 0:
        return []

    selection_count = min(len(chunks), max_points)
    if selection_count == len(chunks):
        return list(enumerate(chunks, start=1))
    if selection_count == 1:
        return [(1, chunks[0])]

    last_index = len(chunks) - 1
    selected_indexes = [
        round(position * last_index / (selection_count - 1))
        for position in range(selection_count)
    ]
    return [(index + 1, chunks[index]) for index in selected_indexes]


def _split_page_section(page: str, section: str, hard_limit: int) -> list[str]:
    section = (section or "").strip()
    if not section:
        return []

    marker = f"=== 第{page}页 ===\n" if page else ""
    whole = f"{marker}{section}".strip()
    if len(whole) <= hard_limit:
        return [whole]

    raw_blocks = [
        block.strip()
        for block in re.split(r"\n\s*\n|" + _QUESTION_SPLIT_PATTERN.pattern, section)
        if block.strip()
    ]
    if len(raw_blocks) < 2:
        raw_blocks = [block.strip() for block in re.split(r"(?<=[。！？；;])\s*", section) if block.strip()]
    if len(raw_blocks) < 2:
        return [whole[:hard_limit]]

    pieces = []
    current_body = ""
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        candidate_body = f"{current_body}\n{block}".strip() if current_body else block
        candidate_text = f"{marker}{candidate_body}".strip()
        if current_body and len(candidate_text) > hard_limit:
            pieces.append(f"{marker}{current_body}".strip())
            current_body = block
            if len(f"{marker}{current_body}".strip()) > hard_limit:
                pieces.extend(_split_oversized_block(page, block, hard_limit))
                current_body = ""
        else:
            current_body = candidate_body

    if current_body:
        pieces.append(f"{marker}{current_body}".strip())

    return pieces


def _split_oversized_block(page: str, block: str, hard_limit: int) -> list[str]:
    marker = f"=== 第{page}页 ===\n" if page else ""
    parts = []
    sentences = [item.strip() for item in re.split(r"(?<=[。！？；;])\s*", block or "") if item.strip()]
    if len(sentences) < 2:
        sentences = [block[i:i + max(hard_limit - len(marker), 200)] for i in range(0, len(block), max(hard_limit - len(marker), 200))]

    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and len(f"{marker}{candidate}".strip()) > hard_limit:
            parts.append(f"{marker}{current}".strip())
            current = sentence
        else:
            current = candidate
    if current:
        parts.append(f"{marker}{current}".strip())
    return parts


def _split_source_blocks(text: str, max_points: int) -> list[str]:
    return [block for block, _page in _split_source_blocks_with_pages(text, max_points)]


def _looks_like_meaningful_short_block(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return False
    return compact.startswith(("题", "Q", "问")) or any(
        token in compact for token in ("是", "作用", "特点", "定义", "原理", "算法", "机制")
    )


def _infer_knowledge_name(block: str, index: int) -> str:
    text = re.sub(r"^\s*(\[\d+\]|\d+[.、]|第[一二三四五六七八九十]+[章节])\s*", "", block).strip()
    first_line = text.split("\n", 1)[0].strip()
    first_sentence = re.split(r"[。！？；;:：]", first_line, maxsplit=1)[0].strip()

    if 4 <= len(first_sentence) <= 28:
        return first_sentence
    if "是指" in text:
        candidate = text.split("是指", 1)[0].strip()
        if 2 <= len(candidate) <= 28:
            return candidate
    if "包括" in text:
        candidate = text.split("包括", 1)[0].strip()
        if 2 <= len(candidate) <= 28:
            return candidate
    if "代码题" in text and any(token in text for token in ("暴力解", "最优解", "考场")):
        return "代码题考场策略"
    if "考场" in text and any(token in text for token in ("时间", "分钟", "跳过")):
        return "考场时间分配与跳题策略"
    if "择校" in text:
        return "择校风险控制经验"
    if any(token in text for token in ("第一轮", "第二轮", "三轮", "基础阶段", "强化阶段", "冲刺阶段")):
        return "复习阶段规划"
    if "模拟" in text and "真题" in text:
        return "真题与模拟训练安排"
    if "笔记" in text:
        return "专业课笔记与复习方法"
    return f"候选知识点{index}"


def _infer_keywords(block: str, name: str) -> list[str]:
    keywords = []
    for item in re.findall(r"[A-Za-z][A-Za-z0-9_+\-./]{2,}", block):
        if item not in keywords:
            keywords.append(item)
    for item in re.findall(r"[\u4e00-\u9fff]{2,8}", block):
        if item not in keywords and item not in name:
            keywords.append(item)
        if len(keywords) >= 8:
            break
    if name and name not in keywords:
        keywords.insert(0, name)
    return keywords[:8]


def _infer_knowledge_type(block: str) -> str:
    if re.match(r"^(?:题\s*)?\d+\s*[.．、:：]|^题\s*\d+", block.strip()):
        return "题目"
    if any(token in block for token in ("心得", "感悟")):
        return "学习心得"
    if any(token in block for token in ("备考", "考场", "真题", "模拟", "刷题", "择校")):
        return "备考经验"
    if any(token in block for token in ("复习阶段", "规划", "笔记", "方法", "策略")):
        return "方法/策略"
    if any(token in block for token in ("方法", "步骤", "流程", "算法", "模型", "网络")):
        return "方法/模型"
    if any(token in block for token in ("定义", "概念", "是指")):
        return "概念"
    if any(token in block for token in ("作用", "意义", "用于", "功能")):
        return "作用/应用"
    return "知识点"


_OUTLINE_QUESTION_RE = re.compile(r"^(?:题\s*)?\d+\s*[.．、:：]|^题\s*\d+")
_OUTLINE_METADATA_RE = re.compile(
    r"(?:出版社|\bPRESS\b|AGRICULTUREPRESS|编著|主编|学习包|书课|配合使用|"
    r"金榜时代|GLIST|上岸|\d+\s*分|1V1|扫码|投币|课程|服务|基础篇|"
    r"复习全书|辅导讲义|严选题|领跑计划|养成笔记|"
    r"数学[一二三1-3、，,\s]+通用)",
    re.IGNORECASE,
)
_OUTLINE_ACADEMIC_RE = re.compile(
    r"(?:概念|原理|结构|机制|方法|算法|模型|理论|函数|极限|连续|导数|微分|积分|"
    r"方程|级数|向量|矩阵|概率|统计|定理|曲线|曲面|系统|网络|进程|存储|协议|"
    r"诊断|治疗|病理|生理|药理|管理|经济|法律|分析)"
)
_OUTLINE_MATH_RE = re.compile(
    r"(?:函数|极限|连续|导数|微分|积分|方程|级数|向量|矩阵|概率|统计|定理|"
    r"曲线|曲面|单调|奇函数|偶函数|周期|有界|多元|线性代数)"
)
_OUTLINE_CS_RE = re.compile(
    r"(?:数据结构|算法|计算机|组成原理|操作系统|网络|CPU|缓存|存储|进程|线程|协议|页表|TLB)"
, re.IGNORECASE)
_OUTLINE_MEDICAL_RE = re.compile(
    r"(?:医学|内科|外科|病理|生理|药理|诊断|治疗|疾病|症状|体征|病原|用药)"
)
_OUTLINE_STRUCTURE_ONLY_RE = re.compile(
    r"^(?:目录|目\s*录|contents?|参考答案|答案|解析|"
    r"[一二三四五六七八九十]+[、.．]\s*(?:选择题|填空题|解答题)\s*[.。]?)$",
    re.IGNORECASE,
)


def _is_outline_question(block: str) -> bool:
    return bool(_OUTLINE_QUESTION_RE.match((block or "").strip()))


def _outline_heading_matches_subject(line: str, subject: str) -> bool:
    clean_subject = (subject or "").strip()
    if clean_subject in {"数一", "数二", "数三"} or "数学" in clean_subject:
        return bool(_OUTLINE_MATH_RE.search(line))
    if "408" in clean_subject or "计算机" in clean_subject:
        return bool(_OUTLINE_CS_RE.search(line))
    if "医学" in clean_subject:
        return bool(_OUTLINE_MEDICAL_RE.search(line))
    return True


def _split_outline_blocks_with_pages(text: str, max_points: int, subject: str = "") -> list[tuple[str, str, str]]:
    questions: list[tuple[int, str, str, str]] = []
    headings: list[tuple[int, str, str, str]] = []
    sequence = 0
    for page, section in _iter_page_sections(text):
        current_heading = ""
        for raw_line in section.splitlines():
            line = raw_line.strip().lstrip("-•· ").strip()
            if not line or line.startswith("【图片型 PDF"):
                continue
            compact = re.sub(r"\s+", "", line)
            if _OUTLINE_METADATA_RE.search(line) or _OUTLINE_STRUCTURE_ONLY_RE.fullmatch(line):
                continue
            if re.fullmatch(r"\d+\s*[.．]\s*[A-DＡ-Ｄ]", line, re.IGNORECASE):
                continue
            sequence += 1
            if _is_outline_question(line):
                questions.append((sequence, line, page, current_heading))
                continue
            if re.fullmatch(r"第[一二三四五六七八九十百零〇\d]+章", compact):
                current_heading = line
                continue
            is_heading = bool(
                re.match(r"^第[一二三四五六七八九十百零〇\d]+章", compact)
                or (_OUTLINE_ACADEMIC_RE.search(line) and 2 <= len(compact) <= 80)
            )
            if not is_heading or not _outline_heading_matches_subject(line, subject):
                continue
            current_heading = line
            headings.append((sequence, line, page, line))

    if not questions:
        selected = headings[:max_points]
    elif not headings:
        selected = questions[:max_points]
    else:
        question_budget = min(len(questions), max(1, max_points // 2))
        selected = questions[:question_budget]
        selected.extend(headings[: max_points - len(selected)])
        if len(selected) < max_points:
            selected.extend(questions[question_budget : question_budget + max_points - len(selected)])
        selected.sort(key=lambda item: item[0])
    return [(block, page, context) for _order, block, page, context in selected[:max_points]]


def _infer_question_name(block: str, context: str = "") -> str:
    number_match = re.match(r"^(?:题\s*)?(\d+)", block.strip())
    number = number_match.group(1) if number_match else ""
    combined = f"{context} {block}"
    if "函数" in combined and any(token in combined for token in ("奇函数", "偶函数", "周期", "单调", "有界")):
        topic = "函数性质判断"
    elif "极限" in combined:
        topic = "函数极限"
    elif "中值定理" in combined:
        topic = "微分中值定理"
    elif any(token in combined for token in ("导数", "微分")):
        topic = "导数与微分"
    elif "积分" in combined:
        topic = "积分计算"
    elif "微分方程" in combined:
        topic = "微分方程"
    elif "级数" in combined:
        topic = "无穷级数"
    else:
        topic = re.sub(r"^第[一二三四五六七八九十百零〇\d]+章\s*", "", context).strip() or "题目"
    return f"{topic}（题{number}）" if number else topic


def _infer_question_style(block: str, context: str = "") -> str:
    combined = f"{context} {block}"
    if re.search(r"[（(]\s*[A-DＡ-Ｄ]\s*[）)]|\bA[.、:]", block, re.IGNORECASE):
        return "选择题"
    if "填空" in combined or "____" in block:
        return "填空题"
    if "解答" in combined:
        return "解答题"
    return "题目"


def _build_fallback_drafts(
    text: str,
    subject: str = "",
    chapter_name: str = "",
    max_points: int = 12,
    outline_mode: bool = False,
):
    drafts = []
    source_blocks = (
        _split_outline_blocks_with_pages(text, max_points, subject=subject)
        if outline_mode
        else _split_source_blocks_with_pages(text, max_points)
    )
    for index, source_item in enumerate(source_blocks, start=1):
        block, page = source_item[:2]
        context = source_item[2] if len(source_item) > 2 else ""
        is_question = outline_mode and _is_outline_question(block)
        name = _infer_question_name(block, context) if is_question else _infer_knowledge_name(block, index)
        if is_question:
            knowledge_type = "题目"
            exam_styles = [_infer_question_style(block, context)]
            source_location = re.match(r"^(题\s*\d+|\d+)", block.strip())
            source_location = source_location.group(1) if source_location else "题目"
            is_ai_expansion = False
            uncertainty_note = ""
        elif outline_mode:
            knowledge_type = "章节提纲"
            exam_styles = []
            source_location = context or "目录"
            is_ai_expansion = False
            uncertainty_note = ""
        else:
            knowledge_type = _infer_knowledge_type(block)
            exam_styles = ["名词解释", "简答题", "材料分析题"]
            source_location = "本地兜底抽取"
            is_ai_expansion = False
            uncertainty_note = "模型调用失败或返回不可解析内容，本条由本地规则基于原文生成，请人工核对。"
        payload = {
            "knowledge_name": name,
            "knowledge_type": knowledge_type,
            "subject": subject,
            "chapter_name": chapter_name,
            "core_definition": block[:800],
            "exam_question_styles": exam_styles,
            "keywords": _infer_keywords(block, name),
            "related_concepts": [],
            "pitfalls": [],
            "example_or_application": "",
            "review_priority": "中",
            "source_text": block[:1200],
            "source_page": f"第{page}页" if page else "",
            "source_location": source_location,
            "tags": [subject, chapter_name, "题目" if is_question else "本地兜底抽取"],
            "mastery_state": "待复习",
            "is_ai_expansion": is_ai_expansion,
            "uncertainty_note": uncertainty_note,
        }
        drafts.append(normalize_knowledge_point_draft(payload))
    return drafts


def _mark_outline_expansions(drafts: list, *, force_expansion: bool = False) -> list:
    marked = []
    for draft in drafts:
        payload = knowledge_point_to_dict(draft)
        if force_expansion:
            core_text = re.sub(r"\s+", "", str(payload.get("core_definition") or ""))
            source_text = re.sub(r"\s+", "", str(payload.get("source_text") or ""))
            generated_details = bool(
                (core_text and source_text and core_text != source_text)
                or payload.get("exam_question_styles")
                or payload.get("related_concepts")
                or payload.get("pitfalls")
                or str(payload.get("example_or_application") or "").strip()
            )
            payload["is_ai_expansion"] = generated_details
            if not generated_details:
                if str(payload.get("knowledge_type") or "").strip() == "题目":
                    payload["knowledge_type"] = "章节提纲"
                marked.append(normalize_knowledge_point_draft(payload))
                continue
        is_question = not force_expansion and (
            str(payload.get("knowledge_type") or "").strip() == "题目"
            or _is_outline_question(str(payload.get("source_text") or ""))
        )
        payload["is_ai_expansion"] = not is_question
        if is_question:
            marked.append(normalize_knowledge_point_draft(payload))
            continue
        note = str(payload.get("uncertainty_note") or "").strip()
        required_note = "基于提纲AI发散，需核对教材"
        payload["uncertainty_note"] = (
            note if required_note in note else f"{required_note}。{note}".rstrip("。")
        )
        marked.append(normalize_knowledge_point_draft(payload))
    return marked


def _dedupe_drafts(drafts: list) -> list:
    deduped = []
    seen = set()
    for draft in drafts:
        payload = knowledge_point_to_dict(draft)
        identity = (
            (payload.get("knowledge_name") or "").strip().lower(),
            (payload.get("source_page") or "").strip(),
            (payload.get("source_location") or "").strip(),
            re.sub(r"\s+", " ", payload.get("source_text") or "").strip()[:80],
        )
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(draft)
    return deduped


_SYLLABUS_HIERARCHY_LINE_RE = re.compile(r"^\[(科目|一级|二级|三级)\]\s*(.+)$")
_SYLLABUS_GENERIC_LEAF_NAMES = {
    "概述", "基本概念", "一般概念", "基本原理", "基本知识", "绪论",
}


def _clean_syllabus_knowledge_name(value: str) -> str:
    cleaned = re.sub(r"^\[(?:科目|一级|二级|三级)\]\s*", "", value or "").strip()
    cleaned = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", cleaned)
    cleaned = re.sub(r"^[（(][\d一二三四五六七八九十百]+[）)]\s*", "", cleaned)
    cleaned = re.sub(r"^\d+[.．、]\s*", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" -—_•·。")


def _build_syllabus_leaf_candidates(text: str, subject: str = "") -> list[dict]:
    """Return only leaf-level outline entries with their full hierarchy paths."""
    candidates: list[dict] = []
    current_page = ""
    current_course = ""
    current_level_one = ""
    current_level_two = ""
    pending_level_two: dict | None = None

    def add_candidate(raw_line: str, value: str, level: str) -> None:
        name = _clean_syllabus_knowledge_name(value)
        if (
            len(re.sub(r"\s+", "", name)) < 3
            or name in _SYLLABUS_GENERIC_LEAF_NAMES
        ):
            return
        path_parts = [item for item in (current_course, current_level_one, current_level_two) if item]
        location = " > ".join(path_parts)
        candidate = {
            "raw_line": raw_line.strip(),
            "knowledge_name": name,
            "knowledge_type": "大纲知识点",
            "subject": subject,
            "chapter_name": " · ".join(
                item for item in (current_course, current_level_one) if item
            ),
            "core_definition": "",
            "exam_question_styles": [],
            "keywords": [],
            "related_concepts": [],
            "pitfalls": [],
            "example_or_application": "",
            "review_priority": "中",
            "source_text": value.strip(),
            "source_page": f"第{current_page}页" if current_page else "",
            "source_location": location or level,
            "tags": [item for item in (current_course, current_level_one) if item],
            "mastery_state": "待复习",
            "is_ai_expansion": False,
            "uncertainty_note": "",
            "bucket": (current_course or subject, current_level_one or current_course or subject),
        }
        identity = (
            candidate["knowledge_name"].lower(),
            candidate["source_location"].lower(),
        )
        if not any(item["identity"] == identity for item in candidates):
            candidate["identity"] = identity
            candidates.append(candidate)

    def flush_level_two() -> None:
        nonlocal pending_level_two
        if pending_level_two and not pending_level_two.get("has_children"):
            add_candidate(
                pending_level_two["raw_line"],
                pending_level_two["value"],
                "二级",
            )
        pending_level_two = None

    for raw in (text or "").splitlines():
        page_match = _PAGE_MARKER_PATTERN.fullmatch(raw.strip())
        if page_match:
            current_page = page_match.group(1)
            continue
        match = _SYLLABUS_HIERARCHY_LINE_RE.match(raw.strip())
        if not match:
            continue
        level, value = match.groups()
        clean_value = _clean_syllabus_knowledge_name(value)
        if level == "科目":
            flush_level_two()
            current_course = clean_value
            current_level_one = ""
            current_level_two = ""
        elif level == "一级":
            flush_level_two()
            current_level_one = clean_value
            current_level_two = ""
        elif level == "二级":
            flush_level_two()
            current_level_two = clean_value
            pending_level_two = {
                "raw_line": raw.strip(),
                "value": value.strip(),
                "has_children": False,
            }
        elif level == "三级":
            if pending_level_two:
                pending_level_two["has_children"] = True
            add_candidate(raw.strip(), value.strip(), "三级")
    flush_level_two()
    for index, candidate in enumerate(candidates, start=1):
        candidate["selection_id"] = f"K{index:03d}"
    return candidates


def _build_syllabus_selection_catalog(text: str, candidates: list[dict]) -> str:
    candidate_ids: dict[str, list[str]] = {}
    for candidate in candidates:
        key = re.sub(r"\s+", "", candidate["raw_line"])
        candidate_ids.setdefault(key, []).append(candidate["selection_id"])

    catalog_lines = []
    used_counts: dict[str, int] = {}
    for raw in (text or "").splitlines():
        key = re.sub(r"\s+", "", raw.strip())
        ids = candidate_ids.get(key) or []
        used_index = used_counts.get(key, 0)
        if used_index < len(ids):
            catalog_lines.append(f"[{ids[used_index]}] {raw.strip()}")
            used_counts[key] = used_index + 1
        else:
            catalog_lines.append(raw)
    return "\n".join(catalog_lines)


def _balanced_syllabus_candidates(
    candidates: list[dict],
    preferred_identities: dict[tuple, int] | None = None,
) -> list[dict]:
    buckets: dict[tuple, list[dict]] = {}
    for candidate in candidates:
        buckets.setdefault(candidate["bucket"], []).append(candidate)
    if preferred_identities:
        unselected_rank = len(preferred_identities) + len(candidates)
        for items in buckets.values():
            items.sort(
                key=lambda item: preferred_identities.get(
                    item["identity"],
                    unselected_rank,
                )
            )
    balanced: list[dict] = []
    while buckets:
        empty_keys = []
        for key, items in buckets.items():
            if items:
                balanced.append(items.pop(0))
            if not items:
                empty_keys.append(key)
        for key in empty_keys:
            buckets.pop(key, None)
    return balanced


def _match_syllabus_selection(payload: dict, candidates: list[dict]) -> dict | None:
    source = re.sub(r"\s+", "", str(payload.get("source_text") or ""))
    name = re.sub(r"\s+", "", _clean_syllabus_knowledge_name(payload.get("knowledge_name") or ""))
    if not source and not name:
        return None
    for candidate in candidates:
        raw_key = re.sub(r"\s+", "", candidate["raw_line"])
        source_key = re.sub(r"\s+", "", candidate["source_text"])
        name_key = re.sub(r"\s+", "", candidate["knowledge_name"])
        if source and source in {raw_key, source_key}:
            return candidate
        if name and name == name_key:
            return candidate
    return None


def _candidate_to_draft(candidate: dict):
    payload = {
        key: value
        for key, value in candidate.items()
        if key not in {"raw_line", "bucket", "identity", "selection_id"}
    }
    return normalize_knowledge_point_draft(payload)


def _extract_syllabus_knowledge_index(
    text: str,
    *,
    subject: str,
    max_points: int,
    llm_callable,
    extraction_guidance: str,
    progress_callback,
):
    """Read one complete syllabus, then select coherent leaf knowledge points."""
    candidates = _build_syllabus_leaf_candidates(text, subject=subject)
    if not candidates:
        return [], ["大纲中没有识别到可用的叶子知识点。"]

    target_count = min(max_points, len(candidates))
    _emit_progress(progress_callback, 1, 3, "正在通读整份大纲并建立层级结构...")
    catalog = _build_syllabus_selection_catalog(text, candidates)
    prompt = build_syllabus_knowledge_index_prompt(
        catalog,
        subject=subject,
        max_points=target_count,
        extraction_guidance=extraction_guidance,
    )
    warnings = []
    selected_candidates: list[dict] = []
    try:
        _emit_progress(progress_callback, 2, 3, "正在从完整大纲中统一筛选知识点...")
        raw_output = llm_callable(prompt)
        selected_ids = list(dict.fromkeys(re.findall(r"\bK\d{3}\b", raw_output.upper())))
        candidate_map = {item["selection_id"]: item for item in candidates}
        selected_candidates = [
            candidate_map[selection_id]
            for selection_id in selected_ids
            if selection_id in candidate_map
        ][:target_count]
    except Exception as exc:
        warnings.append(f"整份大纲筛选失败，已按原文叶子层级整理：{exc}")

    # Honor the model's priorities inside each chapter, while round-robin
    # balancing all chapters prevents a lazy sequential answer from selecting
    # only the first subject in the document.
    preferred_identities = {
        item["identity"]: rank for rank, item in enumerate(selected_candidates)
    }
    selected_candidates = _balanced_syllabus_candidates(
        candidates,
        preferred_identities=preferred_identities,
    )[:target_count]

    _emit_progress(progress_callback, 3, 3, f"已整理 {len(selected_candidates)} 个大纲知识点")
    return [_candidate_to_draft(item) for item in selected_candidates], warnings


def _emit_progress(
    progress_callback: Callable[[int, int, str], None] | None,
    current: int,
    total: int,
    message: str,
) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(current, total, message)
    except Exception:
        return


def extract_knowledge_points_as_drafts(
    text: str,
    subject: str = "",
    chapter_name: str = "",
    max_points: int = 12,
    llm_callable=None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    extraction_guidance: str = "",
    outline_mode: bool = False,
):
    warnings = []
    if llm_callable is None:
        return [], ["未提供 LLM 调用函数，无法执行知识点提取。"]

    safe_text = (text or "").strip()
    if not safe_text:
        return [], ["输入文本为空，无法提取知识点。"]
    syllabus_outline_mode = outline_mode and "考试大纲提纲" in safe_text

    if syllabus_outline_mode:
        return _extract_syllabus_knowledge_index(
            safe_text,
            subject=subject,
            max_points=max_points,
            llm_callable=llm_callable,
            extraction_guidance=extraction_guidance,
            progress_callback=progress_callback,
        )

    _emit_progress(progress_callback, 0, 1, "正在整理待抽取文本...")
    chunks = (
        _split_text_for_llm(safe_text, target_chars=800, hard_limit=1000)
        if outline_mode
        else _split_text_for_llm(safe_text)
    )
    selected_chunks = _select_chunks_for_point_budget(chunks, max_points)
    sampled_chunks = len(selected_chunks) < len(chunks)
    if sampled_chunks:
        skipped_count = len(chunks) - len(selected_chunks)
        selected_positions = "、".join(str(source_index) for source_index, _chunk in selected_chunks)
        if len(selected_chunks) >= 3:
            coverage_description = "覆盖首段、中段和末段"
        elif len(selected_chunks) == 2:
            coverage_description = "覆盖首段和末段"
        else:
            coverage_description = "仅覆盖首段"
        warnings.append(
            f"资料较长，共切分为 {len(chunks)} 个片段；受最多 {max_points} 条知识点限制，"
            f"本次按全篇位置均匀选取 {len(selected_chunks)} 个片段抽取（原文第 {selected_positions} 段），"
            f"{coverage_description}。"
            f"其余 {skipped_count} 个片段本次未逐段调用模型。"
        )
    elif len(chunks) > 1:
        warnings.append(f"资料较长，已按 {len(chunks)} 个片段分段抽取，避免后页内容被截断。")

    total_steps = max(3, len(selected_chunks) * 3 + 2)
    current_step = 1
    if sampled_chunks:
        chunk_message = f"已从全篇 {len(chunks)} 个片段中均匀选取 {len(selected_chunks)} 个抽取片段"
    else:
        chunk_message = f"已整理为 {len(chunks)} 个抽取片段" if len(chunks) > 1 else "已整理抽取文本，准备开始归纳"
    _emit_progress(progress_callback, current_step, total_steps, chunk_message)

    all_drafts = []
    used_fallback = False
    for index, (source_chunk_index, chunk) in enumerate(selected_chunks, start=1):
        if len(all_drafts) >= max_points:
            break

        remaining = max_points - len(all_drafts)
        chunks_left = len(selected_chunks) - index + 1
        chunk_points = max(1, math.ceil(remaining / max(chunks_left, 1)))
        if outline_mode:
            # Keep each JSON response small enough to avoid truncation.
            chunk_points = min(chunk_points, 6)
        chunk_label = (
            f"选中片段 {index}/{len(selected_chunks)}（原文第 {source_chunk_index}/{len(chunks)} 段）"
            if sampled_chunks
            else f"第 {index}/{len(selected_chunks)} 段"
        )
        warning_label = f"原文第 {source_chunk_index} 段" if sampled_chunks else f"第 {index} 段"
        current_step += 1
        _emit_progress(
            progress_callback,
            current_step,
            total_steps,
            f"正在准备{chunk_label}，目标抽取 {min(chunk_points, remaining)} 条候选知识点",
        )
        prompt = build_knowledge_json_prompt(
            chunk,
            subject=subject,
            chapter_name=chapter_name,
            max_points=min(chunk_points, remaining),
            extraction_guidance=extraction_guidance,
            outline_mode=outline_mode,
        )

        try:
            current_step += 1
            _emit_progress(
                progress_callback,
                current_step,
                total_steps,
                f"正在抽取{chunk_label}候选知识点...",
            )
            raw_output = llm_callable(prompt)
        except Exception as exc:
            warnings.append(f"{warning_label}调用模型失败：{exc}")
            fallback_drafts = _build_fallback_drafts(
                chunk,
                subject=subject,
                chapter_name=chapter_name,
                max_points=min(chunk_points, remaining),
                outline_mode=outline_mode,
            )
            used_fallback = used_fallback or bool(fallback_drafts)
            all_drafts.extend(fallback_drafts)
            current_step += 1
            fallback_count = len(fallback_drafts)
            _emit_progress(
                progress_callback,
                current_step,
                total_steps,
                f"{chunk_label}模型失败，已切换本地兜底并生成 {fallback_count} 条草稿",
            )
            continue

        drafts, parse_warnings = parse_knowledge_points_json(raw_output, max_points=min(chunk_points, remaining))
        if outline_mode:
            drafts = _mark_outline_expansions(
                drafts,
                force_expansion=syllabus_outline_mode,
            )
        warnings.extend([f"{warning_label}：{warning}" for warning in parse_warnings])

        if not drafts:
            fallback_drafts = _build_fallback_drafts(
                chunk,
                subject=subject,
                chapter_name=chapter_name,
                max_points=min(chunk_points, remaining),
                outline_mode=outline_mode,
            )
            if fallback_drafts:
                warnings.append(f"{warning_label}模型输出无法解析，已启用本地兜底抽取。")
                used_fallback = True
            all_drafts.extend(fallback_drafts)
            current_step += 1
            _emit_progress(
                progress_callback,
                current_step,
                total_steps,
                f"{chunk_label}已用本地规则补齐，当前累计 {len(all_drafts)} 条草稿",
            )
            continue

        all_drafts.extend(drafts)
        current_step += 1
        _emit_progress(
            progress_callback,
            current_step,
            total_steps,
            f"{chunk_label}完成，当前累计 {len(all_drafts)} 条候选知识点",
        )

    current_step += 1
    _emit_progress(progress_callback, current_step, total_steps, "正在去重并整理候选知识点...")
    deduped = _dedupe_drafts(all_drafts)[:max_points]
    if not deduped and chunks:
        fallback_drafts = _build_fallback_drafts(
            safe_text,
            subject=subject,
            chapter_name=chapter_name,
            max_points=max_points,
            outline_mode=outline_mode,
        )
        if fallback_drafts:
            warnings.append("所有片段均未成功返回可用结果，已启用本地兜底抽取，生成的草稿需要人工核对后再保存。")
        _emit_progress(progress_callback, total_steps, total_steps, f"抽取完成，已生成 {len(fallback_drafts)} 条候选知识点")
        return fallback_drafts, warnings

    if used_fallback:
        warnings.append("已启用本地兜底抽取，生成的草稿需要人工核对后再保存。")

    _emit_progress(progress_callback, total_steps, total_steps, f"抽取完成，已整理出 {len(deduped)} 条候选知识点")
    return deduped, warnings
