"""Serving uploaded files, which live in the database (see apps/filestore).

Two things used to stop a document from opening anywhere but a download:

* every response was marked `Content-Disposition: attachment`, so the in-app
  viewer's frame fetched a download instead of a page, and
* `X-Frame-Options: DENY` stopped the portal, which lives on another host, from
  framing the file at all.

Uploads are limited to PDF and image files, checked by extension, declared type
and the file's first bytes (see apps/applications/uploads.py). Serving does not
rely on that alone: the type sent back is decided here from the file's
extension, never from what was stored, and only PDFs and images are shown
inline. Anything else is sent as an inert download under a sandboxing policy,
so a file that slipped past validation can never run as a page on this origin.

Every stored name contains a random folder and a new upload always gets a new
name, so a response never changes and the browser may keep it. It is marked
private, so no shared cache between the browser and here holds a copy.
"""

from pathlib import PurePosixPath
from urllib.parse import quote

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_GET

from apps.filestore.models import StoredFile


# What may be shown in the browser, and the only type each is served as.
INLINE_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


def _frame_ancestors():
    origins = {"'self'"}
    for origin in [getattr(settings, "FRONTEND_URL", ""), *getattr(settings, "CORS_ALLOWED_ORIGINS", [])]:
        origin = (origin or "").strip().rstrip("/")
        if origin.startswith(("http://", "https://")):
            origins.add(origin)
    return " ".join(sorted(origins))


@require_GET
@xframe_options_exempt
def serve_media(request, path):
    row = StoredFile.objects.filter(name=path).only("content", "content_type", "size").first()
    if row is None:
        raise Http404("No such file.")

    name = PurePosixPath(path).name
    inline_type = INLINE_TYPES.get(PurePosixPath(name).suffix.lower())
    # Anything that is not a PDF or an image (a staff letter in .docx, or a
    # file that predates upload checks) is an opaque download. It is never
    # given a type a browser would render, whatever was stored for it.
    content_type = inline_type or "application/octet-stream"
    response = HttpResponse(bytes(row.content), content_type=content_type)
    response["Content-Length"] = str(row.size)
    # ?download=1 saves the file instead of showing it: a Download button on
    # another origin cannot rely on the <a download> attribute.
    disposition = "inline" if inline_type and not request.GET.get("download") else "attachment"
    response["Content-Disposition"] = f"{disposition}; filename*=UTF-8''{quote(name)}"
    response["X-Content-Type-Options"] = "nosniff"
    policy = f"frame-ancestors {_frame_ancestors()}"
    if not inline_type:
        policy = f"default-src 'none'; sandbox; {policy}"
    response["Content-Security-Policy"] = policy
    response["Cache-Control"] = "private, max-age=604800, immutable"
    return response
