"""Render ExportBundle as a PDF using reportlab."""

from __future__ import annotations

import re
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.export.models import ExportBundle

_LINK_RE = re.compile(r"(https?://\S+)")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _linkify(text: str) -> str:
    escaped = _escape(text)
    return _LINK_RE.sub(r'<a href="\1" color="blue">\1</a>', escaped)


def render_pdf(bundle: ExportBundle) -> bytes:
    """Return PDF bytes for the given export bundle."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=f"WhatsNews Briefing {bundle.export_date}",
        author="WhatsNews",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BriefingTitle",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=6,
        textColor=colors.HexColor("#111111"),
    )
    subtitle_style = ParagraphStyle(
        "BriefingSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#555555"),
        spaceAfter=18,
    )
    topic_style = ParagraphStyle(
        "TopicHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=14,
        spaceAfter=8,
        textColor=colors.HexColor("#1a1a1a"),
    )
    article_title_style = ParagraphStyle(
        "ArticleTitle",
        parent=styles["Heading3"],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#222222"),
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
        alignment=TA_LEFT,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        spaceAfter=2,
    )
    url_style = ParagraphStyle(
        "Url",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#2563eb"),
        spaceAfter=10,
    )

    story = []

    story.append(Paragraph("WhatsNews Daily Briefing", title_style))
    story.append(Paragraph(f"Export date: {bundle.export_date}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 12))

    for topic in bundle.topics:
        story.append(
            Paragraph(
                f"{topic.topic.upper()} &mdash; {topic.report_date}",
                topic_style,
            )
        )

        for article in topic.articles:
            story.append(
                Paragraph(
                    f"{article.position}. {_escape(article.title)}",
                    article_title_style,
                )
            )
            if article.source:
                story.append(
                    Paragraph(f"Source: {_escape(article.source)}", label_style)
                )
            if article.summary:
                story.append(
                    Paragraph(f"<b>Summary:</b> {_escape(article.summary)}", body_style)
                )
            if article.why_it_matters:
                story.append(
                    Paragraph(
                        f"<b>Why it matters:</b> {_escape(article.why_it_matters)}",
                        body_style,
                    )
                )
            link = article.url or article.raw_url
            if link:
                story.append(Paragraph(_linkify(link), url_style))

        story.append(Spacer(1, 8))

    doc.build(story)
    return buffer.getvalue()
