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
            # in front of the site must not hold it; the media view may still let
            # the person's own browser keep it.
            response.headers.setdefault("Cache-Control", "private, max-age=0, no-store")
        return response



class ServerTimingMiddleware:
    """Say how long the server took, and how much of that was the database.

    Browsers show it in the Network panel (Timing tab), which makes a slow
    page easy to place: the app, the database, or the network between.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time

        from django.db import connection

        started = time.perf_counter()
        db_time = [0.0]

        def timed(execute, sql, params, many, context):
            begun = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                db_time[0] += time.perf_counter() - begun

        with connection.execute_wrapper(timed):
            response = self.get_response(request)
        total = (time.perf_counter() - started) * 1000
        response["Server-Timing"] = f"app;dur={total:.1f}, db;dur={db_time[0] * 1000:.1f}"
        return response


class CatalogGZipMiddleware:
    """Compress the public course catalogue, which is the largest JSON sent.

    Limited to /api/catalog/ on purpose: those responses are public and carry
    no secrets, so compressing them cannot leak anything (the BREACH attack
    needs a secret and attacker-controlled text in the same response).
    """

    def __init__(self, get_response):
        from django.middleware.gzip import GZipMiddleware

        self.get_response = get_response
        self.gzip = GZipMiddleware(get_response)

    def __call__(self, request):
        if request.path.startswith("/api/catalog/"):
            return self.gzip(request)
        return self.get_response(request)
