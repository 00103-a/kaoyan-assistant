from __future__ import annotations

import html
import io
import os
import re
from datetime import datetime
from pathlib import Path


_LEADING_BOILERPLATE = (
    "请根据已选资料",
    "请根据所选资料",
    "根据您提供的",
    "根据你提供的",
    "根据已选资料",
    "根据所选资料",
    "基于您提供的",
    "基于你提供的",
    "基于已选资料",
    "基于所选资料",
    "以下是根据",
    "下面我将",
)

_TRAILING_BOILERPLATE = (
    "希望以上",
    "希望这些",
    "如需进一步",
    "如需更多",
    "如果您还需要",
    "如果你还需要",
    "如果需要进一步",
    "以上就是",
    "以上便是",
)


def _register_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular_name = "ChatAnswerCN"
    bold_name = "ChatAnswerCN-Bold"
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


def clean_chat_answer_for_export(answer: str) -> str:
    """Remove conversational filler while keeping the substantive Markdown answer."""
    text = str(answer or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    text = re.sub(r"^(?:好的|当然可以|没问题)[！!，,。:\s：]*", "", text).strip()
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]

    # Long answers often begin by repeating the source and the user's request.
    # Remove that whole opening paragraph only when substantive paragraphs follow it.
    while len(paragraphs) > 1 and paragraphs[0].lstrip("#* ").startswith(_LEADING_BOILERPLATE):
        paragraphs.pop(0)

    while len(paragraphs) > 1 and paragraphs[-1].lstrip("#* ").startswith(_TRAILING_BOILERPLATE):
        paragraphs.pop()

    cleaned = "\n\n".join(paragraphs).strip()
    cleaned = re.sub(r"^(?:回答|答复|正文)\s*[：:]\s*", "", cleaned)
    return cleaned.strip()


def derive_chat_pdf_title(subject: str, prompt: str = "") -> str:
    subject_name = str(subject or "专业课").strip() or "专业课"
    prompt_text = str(prompt or "")
    if "知识框架" in prompt_text or "知识体系" in prompt_text:
        suffix = "知识框架"
    elif "高频考点" in prompt_text or "典型考法" in prompt_text:
        suffix = "高频考点"
    elif "复习清单" in prompt_text or "复习计划" in prompt_text:
        suffix = "复习清单"
    else:
        suffix = "资料问答"
    return f"{subject_name}{suffix}"


def chat_answer_pdf_filename(subject: str, prompt: str = "") -> str:
    title = derive_chat_pdf_title(subject, prompt)
    safe_title = re.sub(r'[\\/:*?"<>|]+', "_", title).strip(" ._") or "专业课资料问答"
    return f"{safe_title}.pdf"


def _markdown_inline(value: str) -> str:
    text = html.escape(str(value or "").strip())
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text.replace("`", "")


def build_chat_answer_pdf(
    answer: str,
    *,
    subject: str,
    prompt: str = "",
    generated_at: datetime | None = None,
) -> bytes:
    """Build a compact A4 PDF from one assistant answer, excluding chat filler."""
    cleaned = clean_chat_answer_for_export(answer)
    if not cleaned:
        raise ValueError("本回答没有可导出的有效内容。")

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    regular_font, bold_font = _register_fonts()
    generated_at = generated_at or datetime.now()
    title = derive_chat_pdf_title(subject, prompt)
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="考研学习助手",
        subject="专业课资料对话精简打印版",
    )

    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "ChatPdfTitle",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=19,
            leading=27,
            textColor=colors.HexColor("#172033"),
            alignment=TA_LEFT,
            spaceAfter=2.5 * mm,
        ),
        "meta": ParagraphStyle(
            "ChatPdfMeta",
            parent=base["Normal"],
            fontName=regular_font,
            fontSize=8.5,
            leading=13,
            textColor=colors.HexColor("#667085"),
            spaceAfter=6 * mm,
        ),
        "h1": ParagraphStyle(
            "ChatPdfH1",
            parent=base["Heading1"],
            fontName=bold_font,
            fontSize=15,
            leading=22,
            textColor=colors.HexColor("#27366F"),
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "ChatPdfH2",
            parent=base["Heading2"],
            fontName=bold_font,
            fontSize=12.5,
            leading=19,
            textColor=colors.HexColor("#172033"),
            spaceBefore=3 * mm,
            spaceAfter=1.5 * mm,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "ChatPdfH3",
            parent=base["Heading3"],
            fontName=bold_font,
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#344054"),
            spaceBefore=2.5 * mm,
            spaceAfter=1 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "ChatPdfBody",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=10,
            leading=16,
            textColor=colors.HexColor("#253047"),
            alignment=TA_LEFT,
            spaceAfter=2.2 * mm,
        ),
        "list": ParagraphStyle(
            "ChatPdfList",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=9.8,
            leading=15.5,
            textColor=colors.HexColor("#253047"),
            leftIndent=6 * mm,
            firstLineIndent=-4 * mm,
            spaceAfter=1.5 * mm,
        ),
    }

    story = [
        Paragraph(_markdown_inline(title), styles["title"]),
        Paragraph(
            f"精简打印版 · {html.escape(generated_at.strftime('%Y-%m-%d %H:%M'))}",
            styles["meta"],
        ),
    ]

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 1.2 * mm))
            continue
        if re.fullmatch(r"[-*_]{3,}", line):
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            style_name = "h1" if level <= 2 else "h2" if level == 3 else "h3"
            story.append(Paragraph(_markdown_inline(heading.group(2)), styles[style_name]))
            continue

        bullet = re.match(r"^[-*+]\s+(.+)$", line)
        if bullet:
            story.append(Paragraph(f"- {_markdown_inline(bullet.group(1))}", styles["list"]))
            continue

        numbered = re.match(r"^(\d+)[.)、]\s*(.+)$", line)
        if numbered:
            story.append(
                Paragraph(
                    f"{numbered.group(1)}. {_markdown_inline(numbered.group(2))}",
                    styles["list"],
                )
            )
            continue

        story.append(Paragraph(_markdown_inline(line), styles["body"]))

    def _draw_page_number(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D6DCE8"))
        canvas.setLineWidth(0.4)
        canvas.line(17 * mm, 12 * mm, A4[0] - 17 * mm, 12 * mm)
        canvas.setFont(regular_font, 8)
        canvas.setFillColor(colors.HexColor("#7A8497"))
        canvas.drawRightString(A4[0] - 17 * mm, 8.5 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    document.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    return output.getvalue()
