"""Serving uploaded files, which live in the database (see apps/filestore).

Two things used to stop a document from opening anywhere but a download:

* every response was marked `Content-Disposition: attachment`, so the in-app
  viewer's frame fetched a download instead of a page, and
* `X-Frame-Options: DENY` stopped the portal, which lives on another host, from
  framing the file at all.

Uploads are limited to PDF and image files, checked by extension, declared type
and the file's first bytes (see apps/applications/uploads.py), so nothing served
here can run script. That makes it safe to show them inline, and to let the
portal's own origins, and no one else, frame them.

Every stored name contains a random folder and a new upload always gets a new
name, so a response never changes and the browser may keep it. It is marked
private, so no shared cache between the browser and here holds a copy.
"""

import mimetypes
from pathlib import PurePosixPath
from urllib.parse import quote

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_GET

from apps.filestore.models import StoredFile


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

    content_type = row.content_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
    response = HttpResponse(bytes(row.content), content_type=content_type)
    name = PurePosixPath(path).name
    response["Content-Length"] = str(row.size)
    # ?download=1 saves the file instead of showing it: a Download button on
    # another origin cannot rely on the <a download> attribute.
    disposition = "attachment" if request.GET.get("download") else "inline"
    response["Content-Disposition"] = f"{disposition}; filename*=UTF-8''{quote(name)}"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = f"frame-ancestors {_frame_ancestors()}"
    response["Cache-Control"] = "private, max-age=604800, immutable"
    return response
