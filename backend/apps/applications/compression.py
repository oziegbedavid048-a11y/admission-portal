"""Make every uploaded file as small as it can be without visible loss.

Uploads are stored in the database (apps/filestore), so every kilobyte saved
here is a kilobyte the database does not carry. Every upload in the project
passes through this module, whoever sent it: an applicant, an agent filing a
student, the desk issuing a letter in the admin, a profile picture, correction
evidence, a support attachment. It is wired as a `pre_save` signal on each model
with a file, so no upload path can skip it.

Two profiles:

* **Profile pictures** are only ever shown small, so they become a 512 pixel
  JPEG at quality 80: typically 25 to 60 KB whatever was uploaded.
* **Documents** must stay readable, so they keep far more detail:
  - photos and scans are turned the right way up, stripped of metadata such as
    GPS location, capped at 2000 pixels on the long side (still sharp for an
    A4 page) and saved as a progressive JPEG at quality 80;
  - PNG screenshots are saved both as an optimised PNG and as a JPEG, and the
    smaller one is kept;
  - iPhone HEIC photos become JPEG, which also means every browser can show
    them;
  - PDFs have their page streams compressed and duplicate objects merged,
    which changes nothing visible, and the pictures inside them (a scanned PDF
    is mostly pictures) get the same 2000 pixel, quality 75 treatment.

The smaller result is kept only if it really is smaller; otherwise the original
is stored. Any failure keeps the original too: compression is never a reason to
lose an upload.
"""

import io
import logging
import time
import warnings
from pathlib import Path

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image as _Image

logger = logging.getLogger(__name__)

# A picture is decoded in full before it is shrunk, so its pixel count, not its
# file size, decides the memory it takes: a small PNG of 13,000 x 13,000 pixels
# unpacks to over 500 MB and would take the server down. 64 megapixels is
# above any phone camera's normal output (a 48 MP photo is 49 million) and
# below anything that hurts. Pillow only warns between the limit and twice it,
# so the warning is made an error; uploads.py refuses such files up front.
MAX_IMAGE_PIXELS = 64_000_000
_Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
warnings.simplefilter("error", _Image.DecompressionBombWarning)

# A PDF longer than this is stored as sent rather than rewritten page by page.
MAX_PDF_PAGES = 150

try:  # iPhone photos. Optional: without it a HEIC upload is stored as sent.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # noqa: BLE001
    pass

PROFILES = {
    "avatar": {"max_side": 512, "quality": 80, "force_jpeg": True},
    "document": {"max_side": 2000, "quality": 80, "force_jpeg": False},
}
PDF_IMAGE_MAX_SIDE = 2000
PDF_IMAGE_QUALITY = 75

# Rewriting a PDF happens while the upload request waits. On a small server a
# long scanned letter took more than the web server's 30 seconds, the request
# was cut off and the desk saw "Internal Server Error" instead of a saved
# letter. Past this budget the PDF is stored exactly as it was sent.
PDF_TIME_BUDGET_SECONDS = 8


class _OverBudget(Exception):
    pass

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")


def _flatten(image):
    """RGB on white, for JPEG, which has no transparency."""
    from PIL import Image

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        base = Image.new("RGB", rgba.size, (255, 255, 255))
        base.paste(rgba, mask=rgba.split()[-1])
        return base
    return image.convert("RGB") if image.mode not in ("RGB", "L") else image


def _jpeg(image, quality):
    out = io.BytesIO()
    _flatten(image).save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


def _compress_image(data, extension, profile):
    """Return (bytes, new extension) or None."""
    from PIL import Image, ImageOps

    settings = PROFILES[profile]
    # Read from memory, so there is no file handle to close, and turned the
    # right way up in place rather than as a second full-size copy.
    image = Image.open(io.BytesIO(data))
    if image.format == "JPEG":
        # Let the decoder scale down while it reads, so a large photo is never
        # held at full size in memory.
        image.draft("RGB", (settings["max_side"], settings["max_side"]))
    ImageOps.exif_transpose(image, in_place=True)
    image.load()
    if max(image.size) > settings["max_side"]:
        image.thumbnail((settings["max_side"], settings["max_side"]), Image.Resampling.LANCZOS)

    quality = settings["quality"]
    if settings["force_jpeg"] or extension in (".jpg", ".jpeg", ".heic", ".heif"):
        return _jpeg(image, quality), ".jpg"
    if extension == ".webp":
        out = io.BytesIO()
        image.save(out, "WEBP", quality=quality, method=6)
        return out.getvalue(), ".webp"
    if extension == ".png":
        png = io.BytesIO()
        image.save(png, "PNG", optimize=True)
        candidates = [(png.getvalue(), ".png"), (_jpeg(image, quality + 5), ".jpg")]
        return min(candidates, key=lambda item: len(item[0]))
    return None


def _compress_pdf(data):
    from PIL import Image
    from pypdf import PdfReader, PdfWriter

    deadline = time.monotonic() + PDF_TIME_BUDGET_SECONDS

    def check_time():
        if time.monotonic() > deadline:
            raise _OverBudget(f"took longer than {PDF_TIME_BUDGET_SECONDS} seconds")

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted or len(reader.pages) > MAX_PDF_PAGES:
        return None
    writer = PdfWriter(clone_from=reader)

    for page in writer.pages:
        check_time()
        try:
            images = list(page.images)
        except Exception:  # noqa: BLE001 - an unusual page keeps its pictures
            images = []
        for embedded in images:
            check_time()
            try:
                picture = embedded.image
                if picture.mode not in ("RGB", "L"):
                    continue  # masks, CMYK and the like are left exactly as they are
                if max(picture.size) > PDF_IMAGE_MAX_SIDE:
                    picture = picture.copy()
                    picture.thumbnail((PDF_IMAGE_MAX_SIDE, PDF_IMAGE_MAX_SIDE), Image.Resampling.LANCZOS)
                embedded.replace(picture, quality=PDF_IMAGE_QUALITY)
            except Exception:  # noqa: BLE001
                continue
        page.compress_content_streams()

    check_time()
    writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    check_time()
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def compress_upload(field_file, profile="document"):
    """Replace a not-yet-saved upload with a smaller copy, when there is one.

    `field_file` is the model's FieldFile. Files already stored are skipped, so
    re-saving a record never re-compresses its file.
    """
    if not field_file or getattr(field_file, "_committed", True):
        return
    upload = field_file.file
    name = Path(field_file.name or getattr(upload, "name", "") or "file").name
    extension = Path(name).suffix.lower()
    if extension not in IMAGE_EXTENSIONS + (".pdf",):
        return

    try:
        upload.seek(0)
        original = upload.read()
        upload.seek(0)
        if extension == ".pdf":
            smaller, new_extension = _compress_pdf(original), ".pdf"
        else:
            result = _compress_image(original, extension, profile)
            smaller, new_extension = result if result else (None, extension)
    except Exception as exc:  # noqa: BLE001 - never lose an upload to this
        logger.warning("Could not compress %s, keeping the original: %s", name, exc)
        return

    # A HEIC photo is converted even if the JPEG is not smaller: browsers cannot
    # show HEIC at all.
    must_convert = extension in (".heic", ".heif")
    if not smaller or (len(smaller) >= len(original) and not must_convert):
        return

    new_name = f"{Path(name).stem}{new_extension}"
    content_type = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(new_extension, "image/jpeg")
    field_file.name = new_name
    field_file.file = InMemoryUploadedFile(
        io.BytesIO(smaller), None, new_name, content_type, len(smaller), None
    )
    logger.info(
        "Compressed %s from %d to %d bytes (%d%% smaller)",
        name, len(original), len(smaller), round(100 - 100 * len(smaller) / len(original)),
    )


def _compressor(fields):
    def handler(sender, instance, **kwargs):
        if kwargs.get("raw"):
            return
        # Remember what a new upload replaces, so the old file can be removed
        # once the record is saved (see _remove_replaced).
        previous = None
        if instance.pk:
            previous = sender.objects.filter(pk=instance.pk).values(*[f for f, _ in fields]).first()
        instance._replaced_files = []
        for field_name, profile in fields:
            field_file = getattr(instance, field_name, None)
            pending = bool(field_file) and not getattr(field_file, "_committed", True)
            old_name = (previous or {}).get(field_name)
            if old_name and (pending or not field_file):
                instance._replaced_files.append((field_name, old_name))
            compress_upload(field_file, profile)
            # A document records its size; record what is actually stored.
            if pending and hasattr(instance, "size_bytes"):
                instance.size_bytes = field_file.file.size

    return handler


def _remove_replaced(sender, instance, **kwargs):
    """After a save, delete the files a new upload replaced."""
    for field_name, old_name in getattr(instance, "_replaced_files", []):
        field = instance._meta.get_field(field_name)
        current = getattr(instance, field_name, None)
        if old_name != getattr(current, "name", None):
            field.storage.delete(old_name)
    instance._replaced_files = []


def _remove_on_delete(fields):
    """Deleting a record deletes its files, so none are left orphaned."""

    def handler(sender, instance, **kwargs):
        for field_name, _ in fields:
            field_file = getattr(instance, field_name, None)
            if field_file and field_file.name:
                field_file.storage.delete(field_file.name)

    return handler


def connect():
    """Attach the compressor and the clean-up to every model that stores an upload."""
    from django.db.models.signals import post_delete, post_save, pre_save

    from apps.accounts.models import SupportTicket, User
    from apps.catalog.models import Institution
    from apps.partners.models import StudentDraftFile
    from apps.payments.models import Payment

    from .models import ApplicationDraftFile, CorrectionRequest, Document, Letter

    targets = [
        (Document, [("file", "document")]),
        (Letter, [("file", "document")]),
        (CorrectionRequest, [("evidence", "document")]),
        (SupportTicket, [("attachment", "document")]),
        (User, [("avatar", "avatar")]),
        (Institution, [("cover_image", "document")]),
        (Payment, [("receipt", "document")]),
        (StudentDraftFile, [("file", "document")]),
        (ApplicationDraftFile, [("file", "document")]),
    ]
    for model, fields in targets:
        pre_save.connect(
            _compressor(fields),
            sender=model,
            weak=False,
            dispatch_uid=f"compress-{model._meta.label_lower}",
        )
        post_save.connect(
            _remove_replaced, sender=model, weak=False,
            dispatch_uid=f"replaced-files-{model._meta.label_lower}",
        )
        post_delete.connect(
            _remove_on_delete(fields), sender=model, weak=False,
            dispatch_uid=f"delete-files-{model._meta.label_lower}",
        )
