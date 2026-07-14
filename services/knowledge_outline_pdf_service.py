from __future__ import annotations

import html
import io
import json
import os
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any


def _register_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular_name = "KnowledgeOutlineCN"
    bold_name = "KnowledgeOutlineCN-Bold"
    if regular_name not in pdfmetrics.getRegisteredFontNames():
        regular_candidates = (
            os.environ.get("KNOWLEDGE_PDF_FONT", ""),
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
        )
        bold_candidates = (
            os.environ.get("KNOWLEDGE_PDF_BOLD_FONT", ""),
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
        )
        regular_path = next((item for item in regular_candidates if item and Path(item).exists()), "")
        bold_path = next((item for item in bold_candidates if item and Path(item).exists()), regular_path)
        if not regular_path:
            raise RuntimeError("未找到可用于生成中文 PDF 的字体，请设置 KNOWLEDGE_PDF_FONT。")
        pdfmetrics.registerFont(TTFont(regular_name, regular_path))
        pdfmetrics.registerFont(TTFont(bold_name, bold_path))
    return regular_name, bold_name


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _paragraph_text(value: Any, fallback: str = "") -> str:
    text = _safe_text(value, fallback)
    return html.escape(text).replace("\n", "<br/>")


def _is_noisy_outline_item(value: str) -> bool:
    compact = "".join(value.lower().split())
    noise_markers = (
        "扫码",
        "咨询>>",
        "加微信",
        "qq群",
        "更多计算机考研资料",
        "候选知识点",
        "未命名知识点",
    )
    return any(marker in compact for marker in noise_markers)


def _json_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return [item for item in items if not _is_noisy_outline_item(item)]
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, list):
        items = [str(item).strip() for item in parsed if str(item).strip()]
        return [item for item in items if not _is_noisy_outline_item(item)]
    items = [item.strip() for item in str(value).replace("，", ",").split(",") if item.strip()]
    return [item for item in items if not _is_noisy_outline_item(item)]


def _group_points(points: list[dict]) -> OrderedDict[str, list[dict]]:
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for point in points:
        group_name = (
            _safe_text(point.get("chapter_name"))
            or Path(_safe_text(point.get("material_filename"), "未分类资料")).stem
            or "未分类资料"
        )
        groups.setdefault(group_name, []).append(point)
    return groups


def _compact_evidence(text: Any, limit: int = 420) -> str:
    compact = " ".join(_safe_text(text).split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def build_knowledge_outline_pdf(
    points: list[dict],
    *,
    subject: str,
    source_count: int = 0,
    generated_at: datetime | None = None,
) -> bytes:
    """Create an A4, print-oriented memorization outline from stored learning entries."""
    if not points:
        raise ValueError("没有可导出的知识条目。")

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    regular_font, bold_font = _register_fonts()
    generated_at = generated_at or datetime.now()
    groups = _group_points(points)
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f"{subject}背诵提纲",
        author="考研学习助手",
        subject="专业课知识库打印提纲",
    )

    base = getSampleStyleSheet()
    styles = {
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=25,
            leading=34,
            textColor=colors.HexColor("#172033"),
            alignment=TA_CENTER,
            spaceAfter=9 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontName=regular_font,
            fontSize=11,
            leading=18,
            textColor=colors.HexColor("#667085"),
            alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading1"],
            fontName=bold_font,
            fontSize=16,
            leading=23,
            textColor=colors.HexColor("#27366F"),
            spaceBefore=4 * mm,
            spaceAfter=3 * mm,
            keepWithNext=True,
        ),
        "entry": ParagraphStyle(
            "Entry",
            parent=base["Heading2"],
            fontName=bold_font,
            fontSize=12,
            leading=18,
            textColor=colors.HexColor("#172033"),
            spaceBefore=3 * mm,
            spaceAfter=1.5 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=9.5,
            leading=15,
            textColor=colors.HexColor("#344054"),
            alignment=TA_LEFT,
            spaceAfter=1.5 * mm,
        ),
        "label": ParagraphStyle(
            "Label",
            parent=base["BodyText"],
            fontName=bold_font,
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#3446A8"),
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#667085"),
        ),
        "warning": ParagraphStyle(
            "Warning",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=8.5,
            leading=13,
            textColor=colors.HexColor("#9A6700"),
            backColor=colors.HexColor("#FFF7D6"),
            borderPadding=6,
            spaceBefore=1 * mm,
            spaceAfter=2 * mm,
        ),
    }

    story = [Spacer(1, 30 * mm)]
    story.append(Paragraph(_paragraph_text(subject), styles["cover_title"]))
    story.append(Paragraph("背诵提纲 · A4 打印版", styles["cover_subtitle"]))
    story.append(Spacer(1, 10 * mm))
    summary_data = [
        [Paragraph("资料范围", styles["label"]), Paragraph(f"{source_count or len(groups)} 份", styles["body"])],
        [Paragraph("知识条目", styles["label"]), Paragraph(f"{len(points)} 条", styles["body"])],
        [Paragraph("提纲章节", styles["label"]), Paragraph(f"{len(groups)} 组", styles["body"])],
        [Paragraph("生成时间", styles["label"]), Paragraph(generated_at.strftime("%Y-%m-%d %H:%M"), styles["body"])],
    ]
    summary_table = Table(summary_data, colWidths=[35 * mm, 85 * mm], hAlign="CENTER")
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F8FC")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D6DCE8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E4E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 10 * mm)])
    story.append(
        Paragraph(
            "打印建议：A4 双面、实际大小。背诵时先遮住“提要”，根据标题口述；再核对关键词和来源。",
            styles["warning"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("提纲目录", styles["section"]))
    for index, (group_name, group_points) in enumerate(groups.items(), start=1):
        story.append(
            Paragraph(
                f"{index}. {_paragraph_text(group_name)}（{len(group_points)} 条）",
                styles["body"],
            )
        )
    story.append(PageBreak())

    entry_number = 0
    for section_index, (group_name, group_points) in enumerate(groups.items(), start=1):
        story.append(Paragraph(f"{section_index}. {_paragraph_text(group_name)}", styles["section"]))
        for point in group_points:
            entry_number += 1
            entry_type = _safe_text(point.get("knowledge_type"), "专业知识")
            title = _safe_text(point.get("knowledge_name"), "未命名条目")
            story.append(
                Paragraph(
                    f"{entry_number}. {_paragraph_text(title)}　<font color='#5267C9'>[{_paragraph_text(entry_type)}]</font>",
                    styles["entry"],
                )
            )
            summary = point.get("core_definition") or point.get("content") or "暂无提要"
            story.append(
                Paragraph(f"<b>提要：</b>{_paragraph_text(summary)}", styles["body"])
            )

            detail_rows = []
            for label, field in (
                ("关键词", "keywords_json"),
                ("常见考法", "exam_question_styles_json"),
                ("易错提醒", "pitfalls_json"),
                ("相关内容", "related_concepts_json"),
            ):
                items = _json_list(point.get(field))
                if items:
                    detail_rows.append(
                        [
                            Paragraph(label, styles["label"]),
                            Paragraph(_paragraph_text(" / ".join(items)), styles["body"]),
                        ]
                    )
            if detail_rows:
                details = Table(detail_rows, colWidths=[23 * mm, 132 * mm], hAlign="LEFT")
                details.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#E7EAF0")),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ]
                    )
                )
                story.extend([details, Spacer(1, 1 * mm)])

            source_bits = [
                item
                for item in (
                    _safe_text(point.get("source_page")),
                    _safe_text(point.get("source_location")),
                    _safe_text(point.get("material_filename")),
                )
                if item
            ]
            source_label = " / ".join(source_bits) or "来源位置未标注"
            story.append(Paragraph(f"<b>来源：</b>{_paragraph_text(source_label)}", styles["small"]))
            evidence = _compact_evidence(point.get("source_text"))
            if evidence:
                story.append(Paragraph(f"<b>依据：</b>{_paragraph_text(evidence)}", styles["small"]))
            if point.get("is_ai_expansion"):
                note = point.get("uncertainty_note") or "本条包含 AI 基于提纲的发散内容，请结合教材核对。"
                story.append(Paragraph(_paragraph_text(note), styles["warning"]))
            story.append(Paragraph("背诵状态：[ ] 未掌握　[ ] 模糊　[ ] 已掌握", styles["small"]))
            story.append(Spacer(1, 2.5 * mm))

    def draw_first_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular_font, 8)
        canvas.setFillColor(colors.HexColor("#98A2B3"))
        canvas.drawCentredString(A4[0] / 2, 9 * mm, "考研学习助手 · 背诵提纲")
        canvas.restoreState()

    def draw_later_pages(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9DEE8"))
        canvas.setLineWidth(0.4)
        canvas.line(17 * mm, A4[1] - 11 * mm, A4[0] - 17 * mm, A4[1] - 11 * mm)
        canvas.setFont(regular_font, 8)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(17 * mm, A4[1] - 9 * mm, f"{subject} · 背诵提纲")
        canvas.drawRightString(A4[0] - 17 * mm, 9 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_first_page, onLaterPages=draw_later_pages)
    return output.getvalue()
