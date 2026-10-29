"""One school's course list as a PDF, for agents to share with students.

Agents download it from the Courses page (as a PDF, or as an image the portal
draws from this same PDF), so both always say the same thing. It carries the
school, where it is, its tuition range and deposit, then every active course
with its level, duration, yearly tuition and notes, page-numbered.

Tuition stays in the school's own currency with its sign (the fee rules).
The application fee is not printed: it is shown to each student in their own
currency when they apply.
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

from apps.applications.dossier import BRAND, INK, LINE, PANEL, QUIET, _header, _text

LEVELS = {
    "bachelors": "Bachelor's",
    "masters": "Master's / MBA",
    "phd": "PhD",
    "diplomas": "Diploma",
    "other": "Other",
}

CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK)
CELL_BOLD = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
CELL_QUIET = ParagraphStyle("cellq", parent=CELL, fontSize=7.5, leading=9.5, textColor=QUIET)
HEAD = ParagraphStyle("head", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
FACT_LABEL = ParagraphStyle("fl", fontName="Helvetica", fontSize=8, leading=10, textColor=QUIET)
FACT_VALUE = ParagraphStyle("fv", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=INK)


def _money(amount, institution):
    if amount is None:
        return "On request"
    symbol = (institution.tuition_symbol or institution.currency or "").strip()
    value = f"{amount:,.0f}" if amount == int(amount) else f"{amount:,.2f}"
    return f"{symbol}{value}" if len(symbol) <= 2 else f"{symbol} {value}"


def _deposit(institution):
    if institution.tuition_deposit_amount:
        return _money(institution.tuition_deposit_amount, institution)
    if institution.tuition_deposit_percent:
        return f"{institution.tuition_deposit_percent:g}% of tuition"
    return "None"


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(QUIET)
    canvas.drawString(doc.leftMargin, 10 * mm, "Gabstep · apply.gabstep.com · Courses and tuition as supplied by the school.")
    canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def course_sheet_pdf(institution):
    """The PDF bytes for this school's course list."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm,
        title=f"{institution.name} courses",
        author="Gabstep",
    )
    country = institution.country.name if institution.country_id else ""
    location = institution.location or country
    if country and country.lower() not in location.lower():
        location = f"{location}, {country}"
    courses = list(institution.programs.all().order_by("display_order", "name"))

    story = _header(_text(institution.name), _text(location, ""))
    facts = Table(
        [[
            [Paragraph("Tuition", FACT_LABEL), Paragraph(_text(institution.tuition_summary, "See each course"), FACT_VALUE)],
            [Paragraph("Tuition deposit", FACT_LABEL), Paragraph(_text(_deposit(institution)), FACT_VALUE)],
            [Paragraph("Courses", FACT_LABEL), Paragraph(str(len(courses)), FACT_VALUE)],
        ]],
        colWidths=[None, None, 28 * mm],
        hAlign="LEFT",
    )
    facts.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [facts, Spacer(1, 6 * mm)]

    rows = [[Paragraph(text, HEAD) for text in ("Course", "Level", "Duration", "Tuition / year")]]
    for course in courses:
        name = [Paragraph(_text(course.name), CELL_BOLD)]
        extra = " · ".join(part for part in (course.qualification_level, course.note) if part)
        if extra:
            name.append(Paragraph(_text(extra), CELL_QUIET))
        rows.append([
            name,
            Paragraph(LEVELS.get(course.level, "Other"), CELL),
            Paragraph(_text(course.duration, "-"), CELL),
            Paragraph(_text(_money(course.tuition, institution)), CELL_BOLD),
        ])
    if len(rows) == 1:
        rows.append([Paragraph("No courses listed yet.", CELL), "", "", ""])

    width = A4[0] - doc.leftMargin - doc.rightMargin
    table = Table(rows, colWidths=[width * 0.55, width * 0.15, width * 0.14, width * 0.16], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PANEL]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
