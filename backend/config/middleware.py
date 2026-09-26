"""Response hardening that belongs to the whole project rather than one app."""


class UploadedFileHeadersMiddleware:
    """Make sure an uploaded file is downloaded, never rendered.

    Uploads are served from the same origin as the portal, so a file the browser
    decides to render runs with the portal's origin: it can read that person's
    storage and call the API as them. The upload validator already refuses
    anything that is not a document, but that is one check, and a single missed
    case should not be enough on its own.

    So every response under MEDIA_URL is marked as an attachment and told not to
    be sniffed. A PDF or an image still opens fine from the download; nothing
    executes in the page's origin either way.

    On a deployment where the web server serves media directly this middleware
    never sees those requests, so the same two headers belong in that server's
    config as well. The note is in the README.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        from django.conf import settings

        self.prefix = settings.MEDIA_URL if settings.MEDIA_URL.startswith("/") else f"/{settings.MEDIA_URL}"

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(self.prefix):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers.setdefault("Content-Disposition", "attachment")
            # An uploaded document is private to one application. A shared cache
            # in front of the site must not hold it.
            response.headers["Cache-Control"] = "private, max-age=0, no-store"
        return response
