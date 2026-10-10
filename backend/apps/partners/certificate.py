"""PDF partnership certificate generator – Apply Gabstep.

Features:
  - Deep emerald (#04231B, #0B5C43) and burnished champagne gold (#C5A059, #D4AF37) palette
  - Authentic Apply Gabstep brand lockup with twin-leaf logo
  - Prestigious official partner medallion badge with gold ribbons in the top-right
  - Interlocking gold and emerald perimeter border with classic corner ornaments
  - Exact citation text from the partnership framework:
      "In recognition of our strategic partnership and shared commitment to excellence,
       innovation, and growth. This partnership represents a strong collaboration dedicated
       to mutual success and industry advancement."
  - Dynamic auto-scaling recipient name with executive gold/emerald anchor bar
  - Dignified printed signatory (Stephen Oziegbe.O, Chief Executive Officer)
  - Partner ID verification credential in medallion badge
"""

import io
import math
import os
from datetime import date
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas as rl_canvas
# ── Palette: Apply Gabstep Brand Colors ───────────────────────────────────────
EMERALD_DEEP   = colors.HexColor("#04231B")   # Core brand deep forest green
EMERALD_ACCENT = colors.HexColor("#0B5C43")   # Brand primary accent green
EMERALD_TINT   = colors.HexColor("#E1F6DD")   # Subtle mint tint
EMERALD_MUTED  = colors.HexColor("#4E635B")   # Muted slate emerald for subtitles

LOGO_GREEN     = colors.HexColor("#107B00")   # Deep forest green from the Apply Gabstep leaf logo
GOLD_METALLIC  = colors.HexColor("#C5A059")   # Burnished champagne gold
GOLD_LIGHT     = colors.HexColor("#E8D19B")   # Highlight gold
GOLD_DARK      = colors.HexColor("#947514")   # Deep shadow gold
GOLD_RIBBON    = colors.HexColor("#D4AF37")   # Bright medal ribbon gold

INK_PRIMARY    = colors.HexColor("#08211B")   # Deepest ink for headings
INK_BODY       = colors.HexColor("#1A3027")   # High-legibility body ink
CANVAS_BG      = colors.HexColor("#FDFCF8")   # Warm ivory / alabaster canvas
WHITE          = colors.HexColor("#FFFFFF")

LEAF_LIME      = colors.HexColor("#65E005")   # Top leaf brand color
LEAF_FOREST    = colors.HexColor("#107B00")   # Bottom leaf brand color


# ── Page Dimensions (Landscape A4) ───────────────────────────────────────────
PAGE_W, PAGE_H = landscape(A4)   # 841.89 x 595.28 points


# ── Helper: Asset Discovery ───────────────────────────────────────────────────
def _get_asset_path(filename: str) -> Optional[str]:
    """Find an asset file in the assets directory."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "assets", filename),
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "assets", filename)
        ),
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "static", filename)
        ),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _get_logo_path() -> Optional[str]:
    """Find the Apply Gabstep logo file."""
    return _get_asset_path("logo.png")


def _get_signature_path() -> Optional[str]:
    """Find the signature image."""
    return _get_asset_path("signature.png")


def _get_stamp_path() -> Optional[str]:
    """Find the stamp image."""
    return _get_asset_path("stamp.png")


# ══════════════════════════════════════════════════════════════════════════════
# 1. BORDER & CORNER ORNAMENTS
# ══════════════════════════════════════════════════════════════════════════════

def _draw_luxurious_borders(c: rl_canvas.Canvas):
    """Draw an executive multi-line border with interlocking deep green corner brackets."""
    # Subtle warm canvas fill
    c.setFillColor(CANVAS_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Inset measurements
    m_out = 22.0
    m_mid = 26.5
    m_in  = 31.0

    # 1. Outer hairline logo green frame
    c.setStrokeColor(LOGO_GREEN)
    c.setLineWidth(0.8)
    c.rect(m_out, m_out, PAGE_W - 2 * m_out, PAGE_H - 2 * m_out, fill=0, stroke=1)

    # 2. Main bold emerald frame
    c.setStrokeColor(EMERALD_DEEP)
    c.setLineWidth(2.6)
    c.rect(m_mid, m_mid, PAGE_W - 2 * m_mid, PAGE_H - 2 * m_mid, fill=0, stroke=1)

    # 3. Inner fine logo green hairline
    c.setStrokeColor(LOGO_GREEN)
    c.setLineWidth(0.6)
    c.rect(m_in, m_in, PAGE_W - 2 * m_in, PAGE_H - 2 * m_in, fill=0, stroke=1)

    # 4. Corner decorative brackets & micro-accents
    corner_arm = 20.0
    corners = [
        (m_in, m_in, 1, 1),                          # Bottom-Left
        (PAGE_W - m_in, m_in, -1, 1),                # Bottom-Right
        (m_in, PAGE_H - m_in, 1, -1),                # Top-Left
        (PAGE_W - m_in, PAGE_H - m_in, -1, -1),      # Top-Right
    ]

    c.setStrokeColor(LOGO_GREEN)
    c.setLineWidth(1.6)
    for cx, cy, sx, sy in corners:
        p = c.beginPath()
        p.moveTo(cx + sx * 4, cy + sy * (4 + corner_arm))
        p.lineTo(cx + sx * 4, cy + sy * 4)
        p.lineTo(cx + sx * (4 + corner_arm), cy + sy * 4)
        c.drawPath(p, fill=0, stroke=1)

        # Deep green corner accent square
        c.setFillColor(LOGO_GREEN)
        c.rect(cx + sx * 6 - (2 if sx > 0 else 0), cy + sy * 6 - (2 if sy > 0 else 0), 2.5, 2.5, fill=1, stroke=0)


# ══════════════════════════════════════════════════════════════════════════════
# 2. BRAND LOCKUP (TOP-LEFT)
# ══════════════════════════════════════════════════════════════════════════

def _draw_brand_lockup(c: rl_canvas.Canvas, org_name: str):
    """Draw the Apply Gabstep leaf logo, company title, and subtitle."""
    logo_path = _get_logo_path()
    start_x = 54.0
    start_y = PAGE_H - 50.0

    logo_w = 28.0
    logo_h = 42.0
    drawn_logo = False

    if logo_path:
        try:
            c.drawImage(
                logo_path,
                start_x,
                start_y - logo_h,
                width=logo_w,
                height=logo_h,
                mask="auto",
                preserveAspectRatio=True,
            )
            drawn_logo = True
        except Exception:
            drawn_logo = False

    if not drawn_logo:
        # High quality vector fallback for the twin leaves
        c.setFillColor(LEAF_LIME)
        p1 = c.beginPath()
        p1.arc(start_x, start_y - 20, start_x + 24, start_y, startAng=45, extent=180)
        p1.close()
        c.drawPath(p1, fill=1, stroke=0)

        c.setFillColor(LEAF_FOREST)
        p2 = c.beginPath()
        p2.arc(start_x + 4, start_y - 40, start_x + 26, start_y - 20, startAng=225, extent=180)
        p2.close()
        c.drawPath(p2, fill=1, stroke=0)

    # Brand typography
    text_x = start_x + logo_w + 12.0

    # Primary brand name
    c.setFont("Helvetica-Bold", 15.0)
    c.setFillColor(EMERALD_DEEP)
    c.drawString(text_x, start_y - 17.0, org_name.upper())

    # Deep green accent rule under brand name
    c.setStrokeColor(LOGO_GREEN)
    c.setLineWidth(1.0)
    name_w = c.stringWidth(org_name.upper(), "Helvetica-Bold", 15.0)
    c.line(text_x, start_y - 22.0, text_x + max(name_w, 120), start_y - 22.0)

    # Tagline
    c.setFont("Helvetica-Bold", 7.0)
    c.setFillColor(EMERALD_MUTED)
    c.drawString(text_x, start_y - 33.0, "THE FUTURE OF STUDENT RECRUITMENT IN AFRICA")


# ══════════════════════════════════════════════════════════════════════════════
# 3. OFFICIAL PARTNER MEDALLION BADGE (TOP-RIGHT)
# ══════════════════════════════════════════════════════════════════════════════

def _draw_partner_badge(c: rl_canvas.Canvas, partner_code: str = ""):
    """Draw a prestige gold & emerald circular seal with draped ribbon tails."""
    bx = PAGE_W - 84.0
    by = PAGE_H - 80.0
    outer_r = 38.0
    inner_r = 31.0

    # 1. Ribbon tails (flowing downwards beneath medal)
    c.setFillColor(GOLD_RIBBON)
    for sign in (-1, 1):
        p = c.beginPath()
        top_x = bx + sign * 9.0
        top_y = by - outer_r + 8.0
        p.moveTo(top_x - 7.0, top_y)
        p.lineTo(top_x + sign * 7.0, by - outer_r - 24.0)  # outer tip
        p.lineTo(top_x + sign * 2.0, by - outer_r - 17.0)  # swallowtail notch
        p.lineTo(top_x - 7.0, by - outer_r - 22.0)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    # 2. Outer scalloped sunburst points
    c.setFillColor(GOLD_METALLIC)
    num_points = 32
    p_burst = c.beginPath()
    for i in range(num_points * 2):
        angle = i * (math.pi / num_points)
        r = outer_r if (i % 2 == 0) else (outer_r - 3.4)
        px = bx + r * math.cos(angle)
        py = by + r * math.sin(angle)
        if i == 0:
            p_burst.moveTo(px, py)
        else:
            p_burst.lineTo(px, py)
    p_burst.close()
    c.drawPath(p_burst, fill=1, stroke=0)

    # 3. Outer gold circular ring
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(1.2)
    c.circle(bx, by, outer_r - 1.8, fill=0, stroke=1)

    # 4. Core disc: deep brand emerald
    c.setFillColor(EMERALD_DEEP)
    c.circle(bx, by, inner_r, fill=1, stroke=0)

    # 5. Inner gold ring with micro star dots
    c.setStrokeColor(GOLD_METALLIC)
    c.setLineWidth(0.7)
    c.circle(bx, by, inner_r - 2.8, fill=0, stroke=1)

    c.setFillColor(GOLD_LIGHT)
    for i in range(16):
        a = i * (2 * math.pi / 16)
        c.circle(bx + (inner_r - 2.8) * math.cos(a), by + (inner_r - 2.8) * math.sin(a), 0.8, fill=1, stroke=0)

    # 6. Badge typography
    c.setFillColor(GOLD_LIGHT)
    c.setFont("Helvetica-Bold", 4.8)
    c.drawCentredString(bx, by + 17.0, "★  ★  ★  ★  ★")

    c.setFont("Helvetica-Bold", 7.2)
    c.drawCentredString(bx, by + 8.0, "OFFICIAL")

    c.setFont("Helvetica-Bold", 9.2)
    c.drawCentredString(bx, by - 3.0, "PARTNER")

    # Divider bar
    c.setStrokeColor(LOGO_GREEN)
    c.setLineWidth(0.6)
    c.line(bx - 14.0, by - 7.5, bx + 14.0, by - 7.5)

    c.setFont("Helvetica-Bold", 5.2)
    c.drawCentredString(bx, by - 15.0, "APPLY GABSTEP")

    c.setFont("Helvetica", 4.2)
    cred_text = f"ID: {partner_code}" if partner_code else "VERIFIED CREDENTIAL"
    c.drawCentredString(bx, by - 21.5, cred_text)


# ══════════════════════════════════════════════════════════════════════════════
# 4. CERTIFICATE MAIN CONTENT & TYPOGRAPHY
# ══════════════════════════════════════════════════════════════════════════════

def _wrap_centered_text(c: rl_canvas.Canvas, text: str, center_x: float, start_y: float, max_w: float, line_h: float, font: str, size: float) -> float:
    """Wrap and draw centered text lines."""
    words = text.split()
    lines = []
    curr = ""
    for w in words:
        test = (curr + " " + w).strip()
        if c.stringWidth(test, font, size) <= max_w:
            curr = test
        else:
            if curr:
                lines.append(curr)
            curr = w
    if curr:
        lines.append(curr)

    c.setFont(font, size)
    y = start_y
    for line in lines:
        c.drawCentredString(center_x, y, line)
        y -= line_h
    return y


def _draw_signature_image(c: rl_canvas.Canvas, x: float, y: float, width: float = 100.0, height: float = 40.0):
    """Draw the real signature image from assets/signature.png."""
    sig_path = _get_signature_path()
    if sig_path:
        try:
            c.drawImage(
                sig_path,
                x,
                y,
                width=width,
                height=height,
                mask="auto",
                preserveAspectRatio=True,
            )
            return True
        except Exception:
            pass
    return False


def _draw_stamp_image(c: rl_canvas.Canvas, x: float, y: float, size: float = 72.0):
    """Draw the official company stamp from assets/stamp.png."""
    stamp_path = _get_stamp_path()
    if stamp_path:
        try:
            c.drawImage(
                stamp_path,
                x,
                y,
                width=size,
                height=size,
                mask="auto",
                preserveAspectRatio=True,
            )
            return True
        except Exception:
            pass
    return False


def _draw_certificate_body(
    c: rl_canvas.Canvas,
    agent_name: str,
    partner_code: str,
    issue_date: date,
    org_name: str,
    signatory_name: str,
    signatory_title: str,
):
    """Draw the title, recipient, citation, and bottom Chief Executive Officer signatory."""
    center_x = PAGE_W / 2.0

    # ── 1. Header Eyebrow ─────────────────────────────────────────────────────
    eyebrow_y = 464.0
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(LOGO_GREEN)
    c.drawCentredString(center_x, eyebrow_y, "ACCREDITED PARTNERSHIP NETWORK")

    # ── 2. Main Certificate Title ─────────────────────────────────────────────
    title_y = 426.0
    c.setFont("Helvetica-Bold", 30.5)
    c.setFillColor(EMERALD_DEEP)
    c.drawCentredString(center_x, title_y, "Corporation Certificate of Partnership")

    # ── 3. Decorative Title Flourish / Accent Divider ─────────────────────────
    div_y = 407.0
    c.setStrokeColor(LOGO_GREEN)
    c.setLineWidth(0.8)
    c.line(center_x - 170.0, div_y, center_x - 18.0, div_y)
    c.line(center_x + 18.0, div_y, center_x + 170.0, div_y)

    # Center diamond emblem
    c.setFillColor(LOGO_GREEN)
    p_diam = c.beginPath()
    p_diam.moveTo(center_x, div_y + 4.5)
    p_diam.lineTo(center_x + 6.5, div_y)
    p_diam.lineTo(center_x, div_y - 4.5)
    p_diam.lineTo(center_x - 6.5, div_y)
    p_diam.close()
    c.drawPath(p_diam, fill=1, stroke=0)

    # Flanking accent dots
    c.circle(center_x - 26.0, div_y, 1.2, fill=1, stroke=0)
    c.circle(center_x + 26.0, div_y, 1.2, fill=1, stroke=0)

    # ── 4. Presentation Subtitle ──────────────────────────────────────────────
    pres_y = 366.0
    c.setFont("Helvetica", 12.0)
    c.setFillColor(EMERALD_MUTED)
    c.drawCentredString(center_x, pres_y, "This certificate is proudly presented to")

    # ── 5. Recipient / Agent Name ─────────────────────────────────────────────
    name_y = 310.0
    name_fs = 36.0
    max_name_w = PAGE_W - 200.0

    current_w = c.stringWidth(agent_name, "Helvetica-Bold", name_fs)
    if current_w > max_name_w:
        name_fs = max(20.0, name_fs * (max_name_w / current_w))
        current_w = c.stringWidth(agent_name, "Helvetica-Bold", name_fs)

    c.setFont("Helvetica-Bold", name_fs)
    c.setFillColor(INK_PRIMARY)
    c.drawCentredString(center_x, name_y, agent_name)

    # ── 6. Name Anchor Bar (Balanced deep green & emerald underline) ──────────
    bar_y = 292.0
    bar_w = min(max(current_w + 60.0, 260.0), PAGE_W - 160.0)

    # Solid emerald bar
    c.setFillColor(EMERALD_DEEP)
    c.rect(center_x - bar_w / 2.0, bar_y - 1.8, bar_w, 3.2, fill=1, stroke=0)

    # Deep green highlight line immediately below
    c.setStrokeColor(LOGO_GREEN)
    c.setLineWidth(1.0)
    c.line(center_x - bar_w / 2.0, bar_y - 4.6, center_x + bar_w / 2.0, bar_y - 4.6)

    # ── 7. Citation Body ──────────────────────────────────────────────────────
    body_text = (
        "In recognition of our strategic partnership and shared commitment to excellence, "
        "innovation, and growth. This partnership represents a strong collaboration dedicated "
        "to mutual success and industry advancement."
    )
    body_y = 242.0
    c.setFillColor(INK_BODY)
    _wrap_centered_text(
        c,
        body_text,
        center_x=center_x,
        start_y=body_y,
        max_w=580.0,
        line_h=20.0,
        font="Helvetica",
        size=11.5,
    )

    # ── 8. Elegant Grounding Divider ──────────────────────────────────────────
    flourish_y = 157.0
    c.setStrokeColor(LOGO_GREEN)
    c.setLineWidth(0.6)
    c.line(center_x - 90.0, flourish_y, center_x - 14.0, flourish_y)
    c.line(center_x + 14.0, flourish_y, center_x + 90.0, flourish_y)

    c.setFillColor(LOGO_GREEN)
    p_diam2 = c.beginPath()
    p_diam2.moveTo(center_x, flourish_y + 3.5)
    p_diam2.lineTo(center_x + 5.0, flourish_y)
    p_diam2.lineTo(center_x, flourish_y - 3.5)
    p_diam2.lineTo(center_x - 5.0, flourish_y)
    p_diam2.close()
    c.drawPath(p_diam2, fill=1, stroke=0)

    c.circle(center_x - 22.0, flourish_y, 1.0, fill=1, stroke=0)
    c.circle(center_x + 22.0, flourish_y, 1.0, fill=1, stroke=0)

    # ══════════════════════════════════════════════════════════════════════════
    # 9. BOTTOM SECTION: [Name ── Sig] on compact rule │ Stamp near right edge
    # ══════════════════════════════════════════════════════════════════════════
    baseline_y = 90.0          # The underline sits here
    sig_img_h  = 44.0          # Signature image height
    sig_img_w  = 100.0         # Signature image width
    stamp_size = 90.0          # Stamp — bigger, near right edge
    name_font  = "Helvetica-Bold"
    name_fs    = 14.5
    gap        = 10.0          # Small gap between name and signature

    name_w = c.stringWidth(signatory_name, name_font, name_fs)

    # The name+sig block is centered on the page
    block_w = name_w + gap + sig_img_w
    block_x = center_x - block_w / 2.0   # Left edge of the name+sig block

    # Positions for name and signature (close together)
    name_x = block_x
    sig_x  = block_x + name_w + gap
    sig_y  = baseline_y + 2.0

    # The rule spans only the name+sig block with a small padding each side
    rule_pad   = 18.0
    rule_left  = block_x - rule_pad
    rule_right = block_x + block_w + rule_pad

    # Stamp — comfortably inset from right and bottom edges
    right_inset = 68.0                         # pull in from the right border
    stamp_x     = PAGE_W - right_inset - stamp_size
    stamp_y     = baseline_y - stamp_size * 0.30   # sits above baseline, not clipped at bottom

    # 1. Signature image
    _draw_signature_image(c, sig_x, sig_y, width=sig_img_w, height=sig_img_h)

    # 2. Printed signatory name — vertically centred beside signature
    c.setFont(name_font, name_fs)
    c.setFillColor(INK_PRIMARY)
    name_y_pos = baseline_y + (sig_img_h / 2.0) - (name_fs / 2.0)
    c.drawString(name_x, name_y_pos, signatory_name)

    # 3. Baseline rule (compact, under name+sig block only)
    c.setStrokeColor(LOGO_GREEN)
    c.setLineWidth(1.2)
    c.line(rule_left, baseline_y, rule_right, baseline_y)

    # 4. Stamp — near right page edge, big and bold
    _draw_stamp_image(c, stamp_x, stamp_y, size=stamp_size)

    # 5. Signatory title — centered below the rule
    rule_center = (rule_left + rule_right) / 2.0
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(EMERALD_DEEP)
    title_text = (signatory_title or "Chief Executive Officer").upper()
    c.drawCentredString(rule_center, baseline_y - 15.0, title_text)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

def build_partnership_certificate_raw(
    agent_name: str,
    partner_code: str = "",
    org_name: str = "Apply Gabstep",
    signatory_name: str = "Stephen Oziegbe.O",
    signatory_title: str = "Chief Executive Officer",
    issue_date: Optional[date] = None,
) -> bytes:
    """Generate raw PDF bytes for a partnership certificate given raw string parameters."""
    if issue_date is None:
        issue_date = date.today()

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=landscape(A4))

    # 1. Luxury borders & corners
    _draw_luxurious_borders(c)

    # 2. Apply Gabstep brand lockup (top-left)
    _draw_brand_lockup(c, org_name)

    # 3. Official Partner medallion badge (top-right)
    _draw_partner_badge(c, partner_code=partner_code)

    # 4. Certificate content & bottom Chief Executive Officer
    _draw_certificate_body(
        c,
        agent_name=agent_name,
        partner_code=partner_code,
        issue_date=issue_date,
        org_name=org_name,
        signatory_name=signatory_name,
        signatory_title=signatory_title,
    )

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def build_partnership_certificate(
    agent_profile,
    org_name: str = "Apply Gabstep",
    signatory_name: str = "Stephen Oziegbe.O",
    signatory_title: str = "Chief Executive Officer",
) -> bytes:
    """Generate raw PDF bytes for a partnership certificate from a Django AgentProfile model."""
    user = agent_profile.user
    agent_name = (
        user.full_name
        or getattr(agent_profile, "agency_name", "")
        or user.email
    )
    partner_code = getattr(agent_profile, "partner_code", "")

    return build_partnership_certificate_raw(
        agent_name=agent_name,
        partner_code=partner_code,
        org_name=org_name,
        signatory_name=signatory_name,
        signatory_title=signatory_title,
        issue_date=date.today(),
    )

