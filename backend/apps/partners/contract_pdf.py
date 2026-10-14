"""The Sales Partnership Contract as a PDF, on the company's own pages.

The contract is the company's Word document, exported to PDF and kept as
``assets/contract_template.pdf``. Its design must not change, so nothing here
redraws the pages. Two things are done to the original instead:

  * The text that differs between agents is taken out of the page itself: the
    agreement date on page 1, and the commission amounts in clause 7 on pages 2
    and 3. Only those text runs are removed; the letterhead, the footer, the
    artwork, the company signature and the stamp are untouched.
  * The agent's details, the new date, the amounts and the agent's signature are
    written on top, in the same typeface, size and colour as the document, on the
    same lines.

The typeface is the one embedded in the template (Segoe UI Semibold), read from
the template at run time. It lacks a handful of characters (J, K, Q, X, Z and
most currency signs), which come from Liberation Sans Bold instead. The Naira
sign is not in either font, so it is drawn as an N with two bars, which is how
the sign is made.
"""

import io
import re
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

import pypdf
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

ASSETS = Path(__file__).resolve().parent / "assets"
TEMPLATE = ASSETS / "contract_template.pdf"
FALLBACK_FONT = ASSETS / "fonts" / "LiberationSans-Bold.ttf"

BODY = "ContractSegoeSemibold"
FALLBACK = "ContractLiberationBold"
SIZE = 11.04          # the document's body size
LEADING = 14.65       # distance between two lines of a paragraph
LEFT = 49.704         # the document's left margin
RIGHT = 510.0         # the widest line in the document ends here
NAIRA = "₦"

# The short rule after "Date:" on page 4, exactly as the template draws it.
DATE_RULE = "83.304 397.32 14.664 0.72 re"

# Baselines of the text runs taken out of the template, by page (0-based).
REMOVED_LINES = {
    0: {661.6},
    1: {341.9, 327.7, 283.5, 268.9, 254.2, 239.6, 210.3, 181.0, 166.4, 151.7, 137.1, 122.4, 356.5, 298.2},
    2: {781.2, 766.5, 751.9, 737.3},
}


# ── Fonts ───────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _register_fonts():
    reader = pypdf.PdfReader(str(TEMPLATE))
    font = reader.pages[1]["/Resources"]["/Font"]["/F1"].get_object()
    data = font["/FontDescriptor"].get_object()["/FontFile2"].get_object().get_data()
    body = TTFont(BODY, io.BytesIO(data))
    pdfmetrics.registerFont(body)
    pdfmetrics.registerFont(TTFont(FALLBACK, str(FALLBACK_FONT)))
    return set(body.face.charToGlyph)


def _font_for(char, covered):
    if char == NAIRA:
        return NAIRA
    return BODY if ord(char) in covered else FALLBACK


def _runs(text, covered):
    """Split text into (font, chars) runs."""
    runs = []
    for char in text:
        font = _font_for(char, covered)
        if runs and runs[-1][0] == font and font != NAIRA:
            runs[-1][1] += char
        else:
            runs.append([font, char])
    return runs


def text_width(text, size=SIZE):
    covered = _register_fonts()
    width = 0.0
    for font, chars in _runs(text, covered):
        width += pdfmetrics.stringWidth("N" if font == NAIRA else chars, BODY if font == NAIRA else font, size)
    return width


def draw_text(c, x, y, text, size=SIZE):
    """Draw one line in the document's typeface, with the fallbacks."""
    covered = _register_fonts()
    for font, chars in _runs(text, covered):
        if font == NAIRA:
            width = pdfmetrics.stringWidth("N", BODY, size)
            c.setFont(BODY, size)
            c.drawString(x, y, "N")
            c.saveState()
            c.setLineWidth(size * 0.075)
            for height in (0.30, 0.47):
                c.line(x - size * 0.06, y + size * height, x + width + size * 0.06, y + size * height)
            c.restoreState()
            x += width
        else:
            c.setFont(font, size)
            c.drawString(x, y, chars)
            x += pdfmetrics.stringWidth(chars, font, size)
    return x


def wrap(text, width=RIGHT - LEFT, size=SIZE):
    lines, line = [], ""
    for word in text.split(" "):
        candidate = f"{line} {word}" if line else word
        if line and text_width(candidate, size) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def fit_size(text, width, size=SIZE, smallest=7.0):
    """The largest size up to `size` at which `text` fits in `width`."""
    while size > smallest and text_width(text, size) > width:
        size -= 0.25
    return size


# ── Wording ─────────────────────────────────────────────────────────────

_ONES = "Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen".split()
_TENS = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()


def _words_below_thousand(n):
    parts = []
    if n >= 100:
        parts.append(f"{_ONES[n // 100]} Hundred")
        n %= 100
    if n >= 20:
        parts.append(_TENS[n // 10] + (f"-{_ONES[n % 10]}" if n % 10 else ""))
    elif n:
        parts.append(_ONES[n])
    return " ".join(parts)


def number_in_words(n):
    """1500 -> "One Thousand Five Hundred". Whole numbers below a billion."""
    n = int(n)
    if n == 0:
        return "Zero"
    parts = []
    for value, name in ((1_000_000, "Million"), (1_000, "Thousand")):
        if n >= value:
            parts.append(f"{_words_below_thousand(n // value)} {name}")
            n %= value
    if n:
        parts.append(_words_below_thousand(n))
    return " ".join(parts)


def naira(amount):
    return f"{NAIRA}{int(amount):,}"


def short_naira(amount):
    """30000 -> "30k", as the document writes it."""
    amount = int(amount)
    return f"{amount // 1000}k" if amount % 1000 == 0 else f"{amount:,}"


def ordinal_date(value):
    day = value.day
    suffix = "th" if 11 <= day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}", value.strftime("%B"), value.year


def clause_seven(terms):
    """The commission paragraphs, as (kind, text) in document order.

    `terms` carries the Naira amounts and, for an agent outside Nigeria, the
    currency and the rate used for the estimates (see contract_terms()).
    """
    reg, visa = terms["registration_ngn"], terms["visa_ngn"]
    total = reg + visa
    cap = reg * 15

    local = terms.get("local")

    def estimate(value_ngn):
        return f"about {local['code']} {local['amounts'][value_ngn]:,}" if local else ""

    def amount(value_ngn, words=False):
        """"N30,000 (Thirty Thousand Naira)" as in the original; outside
        Nigeria the local estimate joins the brackets."""
        if words:
            inside = f"{number_in_words(value_ngn)} Naira"
            if local:
                inside += f", {estimate(value_ngn)}"
            return f"{naira(value_ngn)} ({inside})"
        return naira(value_ngn) + (f" ({estimate(value_ngn)})" if local else "")

    blocks = [
        ("head", "a. Admission Sales Commission:"),
        ("para", f"The Sales Partner shall earn {amount(reg, words=True)} for every confirmed admission application sale fully paid on the platform."),
        ("gap", ""),
        ("head", "b. Visa Support Lead Transfer Commission:"),
        ("para", "After admission is granted, when the Sales Partner transfers the same client (or a new qualified lead) to the Visa Support Department for visa processing and that service is confirmed and fully paid, the Sales Partner shall earn an additional "
         f"{amount(visa, words=True)} per closed sale."),
        ("gap", ""),
        ("para", f"Total earning per client that completes both stages = {naira(total)} ({short_naira(reg)} + {short_naira(visa)})"
         + (f", {estimate(total)}." if local else ".")),
        ("gap", ""),
        ("head", "c. Monthly Income Illustration (Not Cap):"),
        ("para", "For transparency, a partner's income scales as follows:"),
        ("para", f"- 1 client (Full cycle) = {amount(total)}"),
        ("para", f"- 3 clients (Full cycle) = {amount(total * 3)}"),
        ("para", f"- 6 clients (Full cycle) = {amount(total * 6)} per month"),
    ]
    cap_text = (
        f"The Company does not cap income at {amount(cap)}. The {NAIRA}{short_naira(cap)} mentioned earlier was based on "
        f"15 direct admission-only sales (15 x {short_naira(reg)}). With the Visa Support commission, partners can "
        f"earn significantly more with fewer clients. All valid commissions above {NAIRA}{short_naira(cap)} will be paid in full."
    )
    return blocks, cap_text


def contract_terms(registration_ngn, visa_ngn, currency="NGN", ngn_per_unit=None):
    """Everything clause 7 needs, with local estimates outside Nigeria."""
    terms = {"registration_ngn": int(registration_ngn), "visa_ngn": int(visa_ngn)}
    if currency and currency.upper() != "NGN" and ngn_per_unit:
        rate = Decimal(ngn_per_unit)
        reg, visa = terms["registration_ngn"], terms["visa_ngn"]
        total = reg + visa

        def convert(value):
            return int((Decimal(value) / rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        # The two commissions are converted; every other figure is built from
        # them, so the estimates add up the way the Naira amounts do.
        local_reg, local_visa = convert(reg), convert(visa)
        local_total = local_reg + local_visa
        terms["local"] = {
            "code": currency.upper(),
            "rate": rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "amounts": {
                reg: local_reg,
                visa: local_visa,
                total: local_total,
                total * 3: local_total * 3,
                total * 6: local_total * 6,
                reg * 15: local_reg * 15,
            },
        }
    return terms


# ── Building the document ───────────────────────────────────────────────


def _strip_lines(page, baselines, rects=()):
    """Remove the text runs sitting on these baselines, and these exact
    rectangle operators, from a page."""
    contents = page.get_contents()
    data = contents.get_data().decode("latin-1")

    def keep(match):
        found = re.search(r"1 0 0 1 [\d.\-]+ ([\d.\-]+) Tm", match.group(0))
        if found and round(float(found.group(1)), 1) in baselines:
            return ""
        return match.group(0)

    data = re.sub(r"BT\b.*?\bET", keep, data, flags=re.S)
    for rect in rects:
        data = data.replace(rect, "")
    contents.set_data(data.encode("latin-1"))
    page.replace_contents(contents)


def _draw_paragraph_block(c, blocks, top):
    """Draw clause 7 from the baseline `top` down. Returns the last baseline."""
    y = top
    first = True
    for kind, text in blocks:
        if kind == "gap":
            y -= LEADING
            continue
        lines = wrap(text) if kind != "head" else [text]
        for line in lines:
            if not first:
                y -= LEADING
            first = False
            draw_text(c, LEFT, y, line)
    return y


def _trimmed(png_bytes):
    """The signature without the empty canvas around it."""
    from PIL import Image

    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    box = image.getchannel("A").getbbox()
    if box:
        pad = 4
        image = image.crop((max(box[0] - pad, 0), max(box[1] - pad, 0),
                            min(box[2] + pad, image.width), min(box[3] + pad, image.height)))
    out = io.BytesIO()
    image.save(out, "PNG")
    out.seek(0)
    return out


def build_contract_pdf(*, name, email, phone, address, signed_on, terms, signature_png=None):
    """The contract with the agent's details filled in.

    `signed_on` is the date written on it. With `signature_png` (a transparent
    PNG) it is the signed contract; without, the copy the agent reads before
    signing.
    """
    _register_fonts()
    reader = pypdf.PdfReader(str(TEMPLATE))
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    width = float(writer.pages[0].mediabox.width)
    height = float(writer.pages[0].mediabox.height)

    for index, baselines in REMOVED_LINES.items():
        _strip_lines(writer.pages[index], baselines)
    if signature_png:
        # The short rule after "Date:" sits under the first digits of a date.
        _strip_lines(writer.pages[3], set(), rects=(DATE_RULE,))

    day, month, year = ordinal_date(signed_on)
    overlay = io.BytesIO()
    c = rl_canvas.Canvas(overlay, pagesize=(width, height))
    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(0, 0, 0)

    # Page 1: the date, and the Sales Partner's details on their lines. A value
    # longer than its line carries the line on underneath it.
    draw_text(c, LEFT, 661.6, f"This Agreement is made on this {day} day of {month}, {year}, BETWEEN:")
    for text, x, y, limit, rule in (
        (name, 88.0, 559.1, RIGHT, (557.45, 261.454)),
        (phone, 90.0, 544.5, 292.0, (542.78, 263.374)),
        (email, 298.5, 544.5, RIGHT + 30, (542.78, 436.01)),
        (address, 98.0, 529.8, RIGHT + 30, (528.14, 267.238)),
    ):
        text = (text or "").strip()
        if not text:
            continue
        end = draw_text(c, x, y, text, fit_size(text, limit - x))
        rule_y, rule_end = rule
        if end + 2 > rule_end:
            c.rect(rule_end - 0.5, rule_y, end + 2.5 - rule_end, 0.72, stroke=0, fill=1)
    c.showPage()

    # Page 2: clause 7.
    blocks, cap_text = clause_seven(terms)
    _draw_paragraph_block(c, blocks, 356.5)
    c.showPage()

    # Page 3: the paragraph that closes clause 7.
    y = 781.2
    for line in wrap(cap_text):
        draw_text(c, LEFT, y, line)
        y -= LEADING
    c.showPage()

    # Page 4: the Sales Partner's signature, name and date.
    if signature_png:
        image = ImageReader(_trimmed(signature_png))
        iw, ih = image.getSize()
        # The band between the "Full Name" line below (its letters rise to about
        # 422) and the "THE SALES PARTNER" heading above (its letters start at
        # 443). A signature is fitted inside it, so a tall flourish never
        # crosses either line.
        box_w, box_h = 170.0, 19.0
        scale = min(box_w / iw, box_h / ih)
        c.drawImage(image, 106.0, 423.5, width=iw * scale, height=ih * scale, mask="auto")
    if name:
        draw_text(c, 128.0, 413.6, name.strip(), fit_size(name.strip(), RIGHT - 128.0))
    if signature_png:
        draw_text(c, 80.0, 399.0, f"{day} {month} {year}")
    c.showPage()
    c.save()

    overlay_reader = pypdf.PdfReader(io.BytesIO(overlay.getvalue()))
    for index, page in enumerate(writer.pages):
        page.merge_page(overlay_reader.pages[index])

    writer.add_metadata({
        "/Title": "Apply Gabstep Sales Partnership Contract",
        "/Author": "Apply Gabstep",
        "/Subject": f"Sales Partnership Contract - {name}",
    })
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
