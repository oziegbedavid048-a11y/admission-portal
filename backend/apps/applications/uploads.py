"""What a person is allowed to upload, and how that is checked.

An applicant uploads a passport page, a transcript and a CV. Before this, the
only check was the file's size, which meant `.html`, `.svg` and `.exe` were all
accepted and then served back from the same origin as the portal under /media/.
An HTML or SVG file served from your own origin runs as your own page: it can
read the signed-in session's storage and call the API as that person. So the
check is in three parts, because each on its own is bypassable:

  * the extension, because that is what the storage layer names the file and
    what a browser sniffs when deciding how to treat it,
  * the declared content type, which catches an honest client sending the wrong
    thing,
  * the first bytes of the file, which catches a dishonest one renaming a
    payload to .pdf.

Anything that passes all three is a document. Anything that fails one is refused
with a reason the person can act on.
"""

from pathlib import Path

from rest_framework import serializers

# Documents an admissions desk actually needs to read, and nothing that a
# browser will ever execute.
ALLOWED = {
    ".pdf": {"application/pdf"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".heic": {"image/heic", "image/heif"},
    ".heif": {"image/heic", "image/heif"},
}

# The first bytes each format begins with. HEIC carries its brand at offset 4,
# so it is checked separately below.
MAGIC = {
    ".pdf": [b"%PDF-"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".webp": [b"RIFF"],
}

HUMAN_LIST = "PDF, JPG, PNG, WEBP or HEIC"


def _looks_like(extension, head):
    if extension in (".heic", ".heif"):
        # ISO base media file: 'ftyp' at offset 4, then a brand such as heic.
        return head[4:8] == b"ftyp"
    if extension == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return any(head.startswith(signature) for signature in MAGIC.get(extension, []))


def validate_upload(uploaded, max_mb):
    """Raise if this file is not a document. Returns the file unchanged."""
    if uploaded is None:
        return uploaded

    if uploaded.size == 0:
        raise serializers.ValidationError("That file is empty.")

    if uploaded.size > max_mb * 1024 * 1024:
        raise serializers.ValidationError(f"Keep the file under {max_mb}MB.")

    extension = Path(uploaded.name or "").suffix.lower()
    if extension not in ALLOWED:
        raise serializers.ValidationError(
            f"That file type is not accepted. Upload a {HUMAN_LIST}."
        )

    declared = (getattr(uploaded, "content_type", "") or "").split(";")[0].strip().lower()
    # A browser sometimes sends nothing, or the catch-all, for a file it does not
    # recognise. That is not proof of anything either way, so it only fails when
    # it actively contradicts the extension.
    if declared and declared not in {"application/octet-stream", ""}:
        if declared not in ALLOWED[extension]:
            raise serializers.ValidationError(
                f"That file says it is {declared} but is named {extension}. "
                "Upload the original file rather than a renamed copy."
            )

    head = uploaded.read(32)
    uploaded.seek(0)
    if not _looks_like(extension, head):
        raise serializers.ValidationError(
            f"That file is not a valid {extension.lstrip('.').upper()}. "
            f"Upload a {HUMAN_LIST}."
        )

    return uploaded


# ── Where an upload is stored ──────────────────────────────────────────
#
# Files used to be saved under their own names, "documents/2026/09/passport.pdf",
# and served from a public URL. Anyone who guessed a common file name could fetch
# someone else's passport. Each file now sits in a folder named by a random
# token, so its address cannot be guessed, and keeps its original name inside
# that folder so a download still arrives as "passport.pdf".


def _stored_name(folder, filename):
    from django.utils import timezone
    from django.utils.crypto import get_random_string
    from django.utils.text import get_valid_filename

    name = get_valid_filename(Path(filename or "file").name) or "file"
    token = get_random_string(24, "abcdefghijklmnopqrstuvwxyz0123456789")
    return f"{folder}/{timezone.now():%Y/%m}/{token}/{name}"


def document_upload_path(instance, filename):
    return _stored_name("documents", filename)


def letter_upload_path(instance, filename):
    return _stored_name("letters", filename)


def correction_upload_path(instance, filename):
    return _stored_name("corrections", filename)


def avatar_upload_path(instance, filename):
    return _stored_name("avatars", filename)


def support_upload_path(instance, filename):
    return _stored_name("support", filename)


def institution_cover_path(instance, filename):
    return _stored_name("institutions", filename)


def receipt_upload_path(instance, filename):
    return _stored_name("receipts", filename)


def draft_upload_path(instance, filename):
    return _stored_name("drafts", filename)
