"""Serving uploaded files from the server's own disk.

Used when uploads are stored on this machine rather than in a bucket. A bucket
serves its own signed links and never reaches this view.

Two things used to stop a document from opening anywhere but a download:

* every response was marked `Content-Disposition: attachment`, so the in-app
  viewer's frame fetched a download instead of a page, and
* `X-Frame-Options: DENY` stopped the portal, which lives on another host, from
  framing the file at all.

Uploads are limited to PDF and image files, checked by extension, declared type
and the file's first bytes (see apps/applications/uploads.py), so nothing served
here can run script. That makes it safe to show them inline, and to let the
portal's own origins, and no one else, frame them.
"""

from pathlib import PurePosixPath
from urllib.parse import quote

from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.static import serve


def _frame_ancestors():
    origins = {"'self'"}
    for origin in [getattr(settings, "FRONTEND_URL", ""), *getattr(settings, "CORS_ALLOWED_ORIGINS", [])]:
        origin = (origin or "").strip().rstrip("/")
        if origin.startswith(("http://", "https://")):
            origins.add(origin)
    return " ".join(sorted(origins))


@xframe_options_exempt
def serve_media(request, path):
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    name = PurePosixPath(path).name
    response["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(name)}"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = f"frame-ancestors {_frame_ancestors()}"
    # An uploaded document is private to one application. A shared cache in
    # front of the site must not hold it.
    response["Cache-Control"] = "private, max-age=0, no-store"
    return response
