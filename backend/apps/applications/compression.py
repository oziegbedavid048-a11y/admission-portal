"""Make every uploaded file smaller before it is stored, without visible loss.

Every upload in the project passes through here, whoever sent it: an applicant
in the wizard or portal, an agent filing a student, the desk issuing a letter in
the admin, a profile picture, a correction's evidence, a support attachment. It
is wired as a `pre_save` signal on each model with a file, so no upload path can
forget to call it.

What happens to each kind of file:

* **JPEG / WEBP photos** are turned the right way up (phones store rotation as
  metadata), stripped of camera metadata such as GPS location, capped at 2560
  pixels on the long side, which is still well above what a scanned page needs to
  stay sharp, and re-encoded at quality 88.
* **PNG** is re-saved with maximum lossless compression. Nothing about the
  pixels changes.
* **PDF** has its page streams compressed losslessly and duplicate objects
  merged. Text, vectors and images inside are left exactly as they were.

The smaller result is kept only if it really is smaller; otherwise the original
is stored untouched. Any failure keeps the original too: compression is never a
reason to lose an upload.
"""

import io
import logging
from pathlib import Path

from django.core.files.uploadedfile import InMemoryUploadedFile

logger = logging.getLogger(__name__)

MAX_SIDE = 2560
JPEG_QUALITY = 88


def _compress_image(data, extension):
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image)
        if max(image.size) > MAX_SIDE:
            image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        if extension in (".jpg", ".jpeg"):
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        elif extension == ".png":
            image.save(out, "PNG", optimize=True)
        elif extension == ".webp":
            image.save(out, "WEBP", quality=JPEG_QUALITY, method=6)
        else:
            return None
        return out.getvalue()


def _compress_pdf(data):
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        return None
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        page.compress_content_streams()
    writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def compress_upload(field_file):
    """Replace a not-yet-saved upload with a smaller copy, when there is one.

    `field_file` is the model's FieldFile. Files already in storage are skipped,
    so re-saving a record never re-compresses (or re-uploads) its file.
    """
    if not field_file or getattr(field_file, "_committed", True):
        return
    upload = field_file.file
    name = Path(field_file.name or getattr(upload, "name", "") or "").name
    extension = Path(name).suffix.lower()
    if extension not in (".jpg", ".jpeg", ".png", ".webp", ".pdf"):
        return

    try:
        upload.seek(0)
        original = upload.read()
        upload.seek(0)
        if extension == ".pdf":
            smaller = _compress_pdf(original)
            content_type = "application/pdf"
        else:
            smaller = _compress_image(original, extension)
            content_type = {
                ".png": "image/png",
                ".webp": "image/webp",
            }.get(extension, "image/jpeg")
    except Exception as exc:  # noqa: BLE001 - never lose an upload to this
        logger.warning("Could not compress %s, keeping the original: %s", name, exc)
        return

    if not smaller or len(smaller) >= len(original):
        return

    field_file.file = InMemoryUploadedFile(
        io.BytesIO(smaller), None, name, content_type, len(smaller), None
    )
    logger.info(
        "Compressed %s from %d to %d bytes (%d%% smaller)",
        name, len(original), len(smaller), round(100 - 100 * len(smaller) / len(original)),
    )


def _compress_fields(*field_names):
    def handler(sender, instance, **kwargs):
        if kwargs.get("raw"):
            return
        for field_name in field_names:
            compress_upload(getattr(instance, field_name, None))

    return handler


def connect():
    """Attach the compressor to every model that stores an upload."""
    from django.db.models.signals import pre_save

    from apps.accounts.models import SupportTicket, User

    from .models import CorrectionRequest, Document, Letter

    targets = [
        (Document, ("file",)),
        (Letter, ("file",)),
        (CorrectionRequest, ("evidence",)),
        (User, ("avatar",)),
        (SupportTicket, ("attachment",)),
    ]
    for model, fields in targets:
        pre_save.connect(
            _compress_fields(*fields),
            sender=model,
            weak=False,
            dispatch_uid=f"compress-{model._meta.label_lower}",
        )
