from __future__ import annotations

import re
from typing import Callable

from services.adaptive_ocr_service import extract_text_adaptively


_HEADING_PATTERNS = (
    re.compile(r"^(?:第[一二三四五六七八九十百零〇\d]+[篇章节部分单元])\s*.*$"),
    re.compile(r"^\d+(?:\.\d+){0,4}[、.．\s]+\S.*$"),
    re.compile(r"^[一二三四五六七八九十百]+[、.．]\s*\S.*$"),
    re.compile(r"^[（(][一二三四五六七八九十\d]+[）)]\s*\S.*$"),
    re.compile(r"^(?:目录|目\s*录|contents?)$", re.IGNORECASE),
)

_NOISE_PATTERN = re.compile(
    r"(?:微信|公众号|二维码|扫码|考研网|版权所有|仅供学习|淘宝|QQ群|www\.|https?://|"
    r"出版社|\bPRESS\b|AGRICULTUREPRESS|编著|主编|学习包|书课|配合使用|B站|"
    r"上岸|\d+\s*分|1V1|投币|课程直击|高效提分|服务全新升级|"
    r"复习全书|辅导讲义|严选题|领跑计划|养成笔记)",
    re.IGNORECASE,
)

_QUESTION_PATTERN = re.compile(r"^(?:题\s*)?\d+\s*[.．、:：]|^题\s*\d+")
_ACADEMIC_SIGNAL_PATTERN = re.compile(
    r"(?:概念|原理|结构|机制|方法|算法|模型|理论|函数|极限|连续|导数|微分|积分|"
    r"方程|级数|向量|矩阵|概率|统计|定理|曲线|曲面|系统|网络|进程|存储|协议|"
    r"诊断|治疗|病理|生理|药理|管理|经济|法律|分析)"
)
_STRUCTURE_ONLY_PATTERN = re.compile(
    r"^(?:目录|目\s*录|contents?|参考答案|答案|解析|"
    r"[一二三四五六七八九十]+[、.．]\s*(?:选择题|填空题|解答题)\s*[.。]?)$",
    re.IGNORECASE,
)

_PAGE_MARKER_PATTERN = re.compile(r"===\s*第\s*(\d+)\s*页\s*===")
_SYLLABUS_TITLE_PATTERN = re.compile(r"(?:考试|招生)?大纲|考查内容|考察内容")
_SYLLABUS_LEVEL_ONE_PATTERN = re.compile(r"^[一二三四五六七八九十百]+[、.．]\s*\S")
_SYLLABUS_LEVEL_TWO_PATTERN = re.compile(r"^[（(][一二三四五六七八九十百]+[）)]\s*\S")
_SYLLABUS_LEVEL_THREE_PATTERN = re.compile(r"^\d+[.．、]\s*\S")
_KNOWN_408_SECTIONS = ("数据结构", "计算机组成原理", "操作系统", "计算机网络")
_SYLLABUS_OBJECTIVE_PATTERN = re.compile(
    r"^[\[【（(]?\s*考[查察]目标\s*[\]】）)]?$"
)


def _syllabus_structure_hits(text: str) -> int:
    return sum(
        bool(
            _SYLLABUS_LEVEL_ONE_PATTERN.match(line)
            or _SYLLABUS_LEVEL_TWO_PATTERN.match(line)
            or _SYLLABUS_LEVEL_THREE_PATTERN.match(line)
        )
        for line in _iter_number_joined_lines(text)
    )


def looks_like_exam_syllabus(text: str, file_name: str = "") -> bool:
    """Detect a structured exam syllabus from its body, never from its filename."""
    # Kept for backward compatibility with older callers. A filename is display
    # metadata and must not decide whether the document is a syllabus.
    del file_name
    compact = re.sub(r"\s+", "", text or "")
    text_signal = bool(_SYLLABUS_TITLE_PATTERN.search(compact))
    structure_hits = _syllabus_structure_hits(text or "")
    section_hits = sum(section in compact for section in _KNOWN_408_SECTIONS)
    objective_signal = "考察目标" in compact or "考查目标" in compact
    return bool(
        text_signal
        and structure_hits >= 5
        and (section_hits >= 2 or objective_signal)
    )


def _iter_number_joined_lines(section: str):
    lines = [re.sub(r"\s+", " ", raw).strip() for raw in (section or "").splitlines()]
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.fullmatch(r"\d+[.．、]", line):
            next_index = index + 1
            while next_index < len(lines) and not lines[next_index]:
                next_index += 1
            if next_index < len(lines):
                line = f"{line}{lines[next_index]}"
                index = next_index
        if line:
            yield line
        index += 1


def _is_syllabus_subject_heading(lines: list[str], index: int) -> bool:
    """Find a course heading from surrounding body structure, not a fixed catalog."""
    line = lines[index]
    compact = re.sub(r"\s+", "", line).strip("-—_•·")
    if compact in _KNOWN_408_SECTIONS:
        return True
    if (
        not compact
        or len(compact) > 30
        or "考查内容" in compact
        or "考察内容" in compact
        or "考查目标" in compact
        or "考察目标" in compact
        or _SYLLABUS_LEVEL_ONE_PATTERN.match(line)
        or _SYLLABUS_LEVEL_TWO_PATTERN.match(line)
        or _SYLLABUS_LEVEL_THREE_PATTERN.match(line)
    ):
        return False

    # A general subject title is normally immediately followed by a course
    # objective block. This supports management, economics, medicine, etc.
    for following in lines[index + 1 : index + 4]:
        following_compact = re.sub(r"\s+", "", following).strip("-—_•·")
        if _SYLLABUS_OBJECTIVE_PATTERN.fullmatch(following_compact):
            return True
        if (
            _SYLLABUS_LEVEL_ONE_PATTERN.match(following)
            or _SYLLABUS_LEVEL_TWO_PATTERN.match(following)
        ):
            break
    return False


def extract_syllabus_outline(text: str, max_items: int = 400) -> tuple[str, dict]:
    """Extract the original hierarchy from a text-readable exam syllabus."""
    page_parts = _PAGE_MARKER_PATTERN.split(text or "")
    if len(page_parts) == 1:
        pages = [("", text or "")]
    else:
        pages = []
        if page_parts[0].strip():
            pages.append(("", page_parts[0]))
        for index in range(1, len(page_parts), 2):
            pages.append((page_parts[index], page_parts[index + 1] if index + 1 < len(page_parts) else ""))

    started = False
    current_subject = ""
    subject_outline_started = False
    seen: set[tuple[str, str]] = set()
    output_pages: list[str] = []
    item_count = 0
    subject_names: list[str] = []

    for page, section in pages:
        page_lines: list[str] = []
        source_lines = list(_iter_number_joined_lines(section))
        for line_index, line in enumerate(source_lines):
            compact = re.sub(r"\s+", "", line).strip("-—_•·")
            if not compact:
                continue
            if "考察内容" in compact or "考查内容" in compact:
                started = True
                continue
            if not started:
                continue

            matched_subject = compact if _is_syllabus_subject_heading(source_lines, line_index) else ""
            if matched_subject:
                current_subject = matched_subject
                subject_outline_started = False
                if current_subject not in subject_names:
                    subject_names.append(current_subject)
                identity = (current_subject, current_subject)
                if identity not in seen:
                    seen.add(identity)
                    page_lines.append(f"[科目] {current_subject}")
                    item_count += 1
                continue

            if not current_subject:
                continue
            if _SYLLABUS_LEVEL_ONE_PATTERN.match(line):
                subject_outline_started = True
                level = "一级"
            elif not subject_outline_started:
                # Skip course objectives and score/exam descriptions before the first chapter.
                continue
            elif _SYLLABUS_LEVEL_TWO_PATTERN.match(line):
                level = "二级"
            elif _SYLLABUS_LEVEL_THREE_PATTERN.match(line):
                level = "三级"
            else:
                continue

            cleaned_line = line.strip(" -—_•·")
            identity = (current_subject, re.sub(r"\s+", "", cleaned_line).lower())
            if identity in seen:
                continue
            seen.add(identity)
            page_lines.append(f"[{level}] {cleaned_line}")
            item_count += 1
            if item_count >= max_items:
                break

        if page_lines:
            marker = f"=== 第{page}页 ===" if page else "=== 大纲 ==="
            output_pages.append(marker + "\n" + "\n".join(page_lines))
        if item_count >= max_items:
            break

    outline_text = "【考试大纲提纲（原文层级抽取）】\n\n" + "\n\n".join(output_pages)
    report = {
        "mode": "syllabus_outline",
        "outline_items": item_count,
        "subjects": subject_names,
        "pages_with_outline": len(output_pages),
    }
    return outline_text.strip() if item_count else "", report


def select_outline_page_indices(page_count: int, max_pages: int = 10) -> list[int]:
    """Prefer likely TOC pages, then sample the rest of the document evenly."""
    page_count = max(0, int(page_count or 0))
    max_pages = max(1, int(max_pages or 1))
    if page_count <= max_pages:
        return list(range(page_count))

    front_count = min(6, max_pages)
    selected = set(range(front_count))
    remaining = max_pages - len(selected)
    if remaining:
        start = front_count
        span = max(page_count - 1 - start, 0)
        for position in range(1, remaining + 1):
            selected.add(round(start + span * position / remaining))
    return sorted(selected)[:max_pages]


def extract_outline_candidates(text: str, max_items: int = 120) -> list[str]:
    """Keep chapter/section-like lines and discard common OCR noise."""
    candidates: list[str] = []
    seen: set[str] = set()
    for raw_line in re.split(r"[\r\n]+", text or ""):
        line = re.sub(r"\s+", " ", raw_line).strip(" \t-—_•·")
        if not line or _NOISE_PATTERN.search(line):
            continue
        compact = re.sub(r"\s+", "", line)
        is_question = bool(_QUESTION_PATTERN.match(line))
        max_length = 220 if is_question else 80
        if not 2 <= len(compact) <= max_length:
            continue
        if re.fullmatch(r"[\d\W_]+", compact):
            continue
        if re.fullmatch(r"\d+\s*[.．]\s*[A-DＡ-Ｄ]", line, re.IGNORECASE):
            continue
        if _STRUCTURE_ONLY_PATTERN.fullmatch(line):
            continue
        looks_like_heading = any(pattern.match(line) for pattern in _HEADING_PATTERNS)
        if is_question:
            looks_like_heading = True
        elif not looks_like_heading:
            looks_like_heading = (
                4 <= len(compact) <= 28
                and not re.search(r"[。！？；;]$", line)
                and len(re.findall(r"[，,：:]", line)) <= 1
                and bool(_ACADEMIC_SIGNAL_PATTERN.search(line))
            )
        if not looks_like_heading:
            continue
        identity = compact.lower()
        if identity in seen:
            continue
        seen.add(identity)
        candidates.append(line)
        if len(candidates) >= max_items:
            break
    return candidates


def _score_outline_page(page_text: str, candidates: list[str]) -> int:
    compact = re.sub(r"\s+", "", page_text or "")
    toc_hits = len(re.findall(r"目录|CONTENTS?", page_text or "", re.IGNORECASE))
    chapter_hits = len(re.findall(r"第[一二三四五六七八九十百零〇\d]+章", compact))
    question_hits = len(re.findall(r"题\s*\d+\s*[:：]", compact))
    academic_hits = sum(bool(_ACADEMIC_SIGNAL_PATTERN.search(item)) for item in candidates)
    promo_hits = len(_NOISE_PATTERN.findall(page_text or ""))
    return toc_hits * 100 + chapter_hits * 18 + question_hits * 10 + academic_hits * 2 - promo_hits * 5


def _fallback_short_lines(text: str, max_items: int) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in re.split(r"[\r\n]+", text or ""):
        line = re.sub(r"\s+", " ", raw_line).strip(" \t-—_•·")
        compact = re.sub(r"\s+", "", line)
        if _NOISE_PATTERN.search(line) or not 4 <= len(compact) <= 45:
            continue
        if len(re.findall(r"[\u4e00-\u9fffA-Za-z]", compact)) < 4:
            continue
        identity = compact.lower()
        if identity in seen:
            continue
        seen.add(identity)
        lines.append(line)
        if len(lines) >= max_items:
            break
    return lines


def extract_pdf_outline_adaptively(
    file_path,
    *,
    progress_callback: Callable[[int, int, str], None] | None = None,
    max_pages: int = 10,
    max_items: int = 120,
) -> tuple[str, dict]:
    """Extract a bounded outline from an image-heavy PDF instead of full-page OCR."""
    import fitz

    doc = fitz.open(str(file_path))
    total_document_pages = len(doc)
    selected_pages = select_outline_page_indices(total_document_pages, max_pages=max_pages)
    page_candidates: list[tuple[int, int, list[str]]] = []
    fallback_pages: list[tuple[int, str]] = []
    engines: list[str] = []
    ocr_pages: list[int] = []

    try:
        total = len(selected_pages)
        for current, page_index in enumerate(selected_pages, start=1):
            if progress_callback:
                progress_callback(
                    current - 1,
                    total,
                    f"正在抽样识别提纲页 {current}/{total}（PDF 第 {page_index + 1} 页）",
                )
            page = doc[page_index]
            native_text = page.get_text("text") or ""
            candidates = extract_outline_candidates(native_text, max_items=max_items)
            page_text = native_text
            engine = "PDFText"

            if len(candidates) < 2:
                pix = page.get_pixmap(dpi=130, alpha=False)
                ocr_result = extract_text_adaptively(pix.tobytes("png"))
                page_text = ocr_result.text or native_text
                candidates = extract_outline_candidates(page_text, max_items=max_items)
                engine = ocr_result.engine
                ocr_pages.append(page_index + 1)

            engines.append(engine)
            fallback_pages.append((page_index + 1, page_text))
            if candidates:
                page_candidates.append(
                    (page_index + 1, _score_outline_page(page_text, candidates), candidates)
                )
    finally:
        doc.close()

    remaining = max_items
    blocks: list[str] = []
    page_candidates.sort(key=lambda item: (-item[1], item[0]))
    for page_number, _score, candidates in page_candidates:
        kept = candidates[:remaining]
        if kept:
            blocks.append(
                f"=== 第{page_number}页 ===\n" + "\n".join(f"- {item}" for item in kept)
            )
            remaining -= len(kept)
        if remaining <= 0:
            break

    used_fallback = False
    if not blocks:
        used_fallback = True
        for page_number, page_text in fallback_pages:
            lines = _fallback_short_lines(page_text, min(remaining, 12))
            if lines:
                blocks.append(
                    f"=== 第{page_number}页 ===\n" + "\n".join(f"- {item}" for item in lines)
                )
                remaining -= len(lines)
            if remaining <= 0:
                break

    if progress_callback:
        progress_callback(len(selected_pages), len(selected_pages), "提纲抽样识别完成")

    primary_engine = max(set(engines), key=engines.count) if engines else "unknown"
    report = {
        "mode": "outline",
        "total_pages": total_document_pages,
        "sampled_pages": [page + 1 for page in selected_pages],
        "pages_processed": len(selected_pages),
        "ocr_pages": ocr_pages,
        "outline_items": max_items - remaining,
        "primary_engine": primary_engine,
        "fallback_short_lines": used_fallback,
    }
    outline_text = "【图片型 PDF 提纲（抽样识别）】\n\n" + "\n\n".join(blocks)
    return outline_text.strip(), report
