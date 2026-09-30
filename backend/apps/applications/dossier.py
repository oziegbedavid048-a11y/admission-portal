"""Printable files about one student: the summary an agent downloads, and the
full download staff take from the admin.

* ``student_summary_pdf`` is one page: who the student is, where they are going,
  and the application reference staff search by.
* ``dossier_zip`` is everything used to register the student. It holds a
  details PDF, one PDF with the details and every document for printing, and a
  Documents folder with each upload in its original format, so any single
  document can still be taken out on its own.

Everything is built in memory when asked for and nothing is written to disk.
"""

import io
import re
import zipfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as PdfImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BRAND = colors.HexColor("#064e3b")
INK = colors.HexColor("#0f172a")
QUIET = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e8f0")
PANEL = colors.HexColor("#f8fafc")

TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=INK)
SUBTITLE = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=10, leading=14, textColor=QUIET)
SECTION = ParagraphStyle(
    "section", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=BRAND, spaceBefore=10, spaceAfter=4
)
LABEL = ParagraphStyle("label", fontName="Helvetica", fontSize=9, leading=12, textColor=QUIET)
VALUE = ParagraphStyle("value", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=INK, alignment=TA_LEFT)
BIG_REF = ParagraphStyle("ref", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=BRAND)
FOOT = ParagraphStyle("foot", fontName="Helvetica", fontSize=8, leading=11, textColor=QUIET)

LOGO = Path(settings.BASE_DIR) / "static" / "admin" / "img" / "gabstep-logo.png"


def _text(value, fallback="Not provided"):
    value = "" if value is None else str(value).strip()
    return (value or fallback).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _course(application):
    names = ", ".join(program.name for program in application.programs.all())
    if names:
        return names
    return application.custom_course_name or "To be confirmed"


def _header(title, subtitle):
    parts = []
    if LOGO.exists():
        logo = PdfImage(str(LOGO), width=9 * mm, height=9 * mm, kind="proportional")
        brand = Table(
            [[logo, Paragraph("<b>Gabstep</b>", ParagraphStyle("b", fontSize=13, textColor=BRAND))]],
            colWidths=[11 * mm, None],
            hAlign="LEFT",
        )
        brand.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        parts.append(brand)
        parts.append(Spacer(1, 6 * mm))
    parts += [Paragraph(title, TITLE), Spacer(1, 1.5 * mm), Paragraph(subtitle, SUBTITLE), Spacer(1, 5 * mm)]
    return parts


def _facts(rows):
    """A two-column label and value table."""
    data = [[Paragraph(_text(label), LABEL), Paragraph(_text(value), VALUE)] for label, value in rows]
    table = Table(data, colWidths=[48 * mm, None], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _build(story):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title="Gabstep", author="Gabstep",
    )
    doc.build(story)
    return buffer.getvalue()


def _footer_line():
    return Paragraph(
        f"Generated {timezone.localtime():%d %B %Y, %H:%M}. Gabstep admissions desk · gabstep.com", FOOT
    )


# ── The one-page summary an agent downloads ─────────────────────────────


def student_summary_pdf(application):
    story = _header("Student summary", "Keep this for your records. Quote the application reference in every enquiry.")

    ref = Table(
        [[Paragraph("Application reference", LABEL)], [Paragraph(_text(application.reference), BIG_REF)]],
        colWidths=[None],
        hAlign="LEFT",
    )
    ref.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (0, 0), 10),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
            ]
        )
    )
    story += [ref, Spacer(1, 6 * mm)]
    # Deliberately short: who, from where, to where, and the reference. No
    # contact details and no documents.
    story.append(
        _facts(
            [
                ("Student name", application.full_name),
                ("Country of origin", application.origin_country.name if application.origin_country else ""),
                ("Destination country", application.destination_country.name if application.destination_country else ""),
            ]
        )
    )
    story += [Spacer(1, 10 * mm), _footer_line()]
    return _build(story)


# ── The full download staff take from the admin ─────────────────────────


def _payment_rows(application):
    payment = getattr(application, "payment", None)
    if payment is None:
        return [("Application fee", "Not paid")]
    rows = [
        ("Application fee", payment.display_total),
        ("Payment status", payment.get_status_display()),
        ("Paid with", payment.gateway),
        ("Payment reference", payment.reference),
    ]
    if payment.paid_at:
        rows.append(("Paid on", f"{timezone.localtime(payment.paid_at):%d %B %Y, %H:%M}"))
    return rows


def details_pdf(application):
    agent = application.submitted_by_agent
    story = _header(
        _text(application.full_name),
        f"Application {_text(application.reference)} · every detail used to register this student",
    )

    story.append(Paragraph("Student", SECTION))
    story.append(
        _facts(
            [
                ("Full name", application.full_name),
                ("Email", application.email),
                ("Phone", application.phone),
                ("Address", application.address),
                ("Country of origin", application.origin_country.name if application.origin_country else ""),
                ("Destination country", application.destination_country.name if application.destination_country else ""),
            ]
        )
    )
    story.append(Paragraph("Education", SECTION))
    story.append(
        _facts(
            [
                ("Institutions attended", application.previous_schools),
                ("Highest qualification", application.qualification),
                ("Year graduated", application.year_graduated),
                ("Grade or CGPA", application.grade_gpa),
            ]
        )
    )
    story.append(Paragraph("University and course", SECTION))
    story.append(
        _facts(
            [
                ("University", application.institution.name if application.institution else "To be confirmed"),
                ("Course", _course(application)),
            ]
        )
    )
    story.append(Paragraph("Payment", SECTION))
    story.append(_facts(_payment_rows(application)))

    if agent is not None:
        story.append(Paragraph("Registered by", SECTION))
        story.append(
            _facts(
                [
                    ("Agent", agent.user.full_name or agent.user.email),
                    ("Agent email", agent.user.email),
                    ("Agent code", agent.partner_code),
                    ("Agency", agent.agency_name),
                ]
            )
        )

    story.append(Paragraph("Status", SECTION))
    story.append(
        _facts(
            [
                ("Application", application.get_status_display()),
                ("Verification", application.get_verification_status_display()),
                ("Visa", application.get_visa_status_display()),
                ("Submitted", f"{timezone.localtime(application.submitted_at):%d %B %Y}" if application.submitted_at else ""),
            ]
        )
    )

    documents = list(application.documents.all())
    story.append(Paragraph("Documents", SECTION))
    if documents:
        story.append(
            _facts(
                [
                    (document.name, f"{document.get_status_display()} · {document.original_filename or 'file'}")
                    for document in documents
                ]
            )
        )
    else:
        story.append(Paragraph("No documents uploaded.", LABEL))

    story += [Spacer(1, 8 * mm), _footer_line()]
    return _build(story)


def _document_as_pdf(data, filename):
    """A document's bytes as PDF pages, or None when it cannot be converted."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        try:
            PdfReader(io.BytesIO(data))
            return data
        except Exception:  # noqa: BLE001 - a broken PDF is left out of the merge, not fatal
            return None
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        out = io.BytesIO()
        image.save(out, format="PDF", resolution=150)
        return out.getvalue()
    except Exception:  # noqa: BLE001
        return None


def _safe(name):
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", name or "").strip().replace(" ", "-")
    return cleaned or "document"


def _read(field):
    field.open("rb")
    try:
        return field.read()
    finally:
        field.close()


def dossier_zip(application):
    """(filename, bytes) for everything about one student."""
    folder = f"{application.reference}_{_safe(application.full_name)}"
    details = details_pdf(application)

    merged = PdfWriter()
    merged.append(PdfReader(io.BytesIO(details)))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{folder}/1_Student-details.pdf", details)

        used = set()
        for document in application.documents.all():
            if not document.file:
                continue
            try:
                data = _read(document.file)
            except Exception:  # noqa: BLE001 - a missing file must not stop the download
                continue
            original = document.original_filename or Path(document.file.name).name
            extension = Path(original).suffix.lower() or Path(document.file.name).suffix.lower()
            base = _safe(document.name)
            name = f"{base}{extension}"
            counter = 2
            while name in used:
                name = f"{base}-{counter}{extension}"
                counter += 1
            used.add(name)
            archive.writestr(f"{folder}/Documents/{name}", data)

            pages = _document_as_pdf(data, name)
            if pages:
                try:
                    merged.append(PdfReader(io.BytesIO(pages)))
                except Exception:  # noqa: BLE001
                    pass

        combined = io.BytesIO()
        merged.write(combined)
        archive.writestr(f"{folder}/2_Everything-in-one.pdf", combined.getvalue())

    return f"{folder}.zip", buffer.getvalue()
