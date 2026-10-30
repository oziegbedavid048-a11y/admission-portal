"""Turning an admin's upload into a landing page review image.

The original visa or letter carries names, passport numbers, addresses and
IDs, so it is never stored. The admin's blur tool (static/admin/landing_reviews)
shows the file in the browser, the admin drags boxes over anything private, and
the browser sends back only the blurred picture. A PDF is turned into a picture
of its first page here first (``pdf_first_page``), in memory, and that answer
is not kept either.

``redacted_image`` checks the picture the browser sent and stores it small: a
WebP at most 960 pixels wide, around 40 to 90 KB, which is all a card or the
full-size viewer on the home page needs.
"""

import base64
import binascii
import io
import re

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image

MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 40_000_000
STORED_WIDTH = 960
DATA_URL = re.compile(r"^data:image/(jpeg|png|webp);base64,(?P<data>[A-Za-z0-9+/=\s]+)$")


def pdf_first_page(upload):
    """PNG bytes of a PDF's first page, about 1600 pixels wide."""
    import pypdfium2 as pdfium

    data = upload.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise ValidationError("That PDF is larger than 15 MB.")
    if not data.startswith(b"%PDF"):
        raise ValidationError("That file is not a PDF.")
    try:
        document = pdfium.PdfDocument(data)
        page = document[0]
        width = page.get_width() or 612
        picture = page.render(scale=min(1600 / width, 4)).to_pil().convert("RGB")
    except Exception as exc:  # noqa: BLE001 - any unreadable PDF
        raise ValidationError("That PDF could not be read.") from exc
    out = io.BytesIO()
    picture.save(out, "PNG", optimize=True)
    return out.getvalue()


def redacted_image(data_url):
    """The blurred picture from the admin's browser, checked and stored as WebP."""
    match = DATA_URL.match((data_url or "").strip())
    if not match:
        raise ValidationError("The blurred image did not come through. Choose the file again.")
    try:
        raw = base64.b64decode(match.group("data"), validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError("The blurred image did not come through. Choose the file again.") from exc
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValidationError("The image is too large.")
    try:
        picture = Image.open(io.BytesIO(raw))
        if picture.width * picture.height > MAX_PIXELS:
            raise ValidationError("The image is too large.")
        picture.load()
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - anything Pillow cannot read
        raise ValidationError("That image could not be read.") from exc
    picture = picture.convert("RGB")
    if picture.width > STORED_WIDTH:
        picture = picture.resize(
            (STORED_WIDTH, round(picture.height * STORED_WIDTH / picture.width)), Image.LANCZOS
        )
    out = io.BytesIO()
    picture.save(out, "WEBP", quality=76, method=6)
    return ContentFile(out.getvalue(), name="review.webp")
