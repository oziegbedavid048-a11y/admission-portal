"""Response hardening that belongs to the whole project rather than one app."""


class UploadedFileHeadersMiddleware:
    """Harden every response under MEDIA_URL, whoever produced it.

    The media view (config/media.py) sets its own headers so a PDF or image can
    be shown inline in the portal. This is the backstop for anything else that
    answers under that prefix: never sniffed, never cached by a shared cache, and
    downloaded rather than rendered unless the view has already said otherwise.

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
