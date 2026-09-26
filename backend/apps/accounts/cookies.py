"""Where the refresh token lives.

Both tokens used to be handed to the browser and kept in `localStorage`. That is
readable by any script running on the page, so a single injected script — one bad
dependency, one reflected value — walks away with a refresh token that stays
valid for a week and can be used from anywhere.

The split now is:

  * the **access** token goes to the browser in the response body and is held in
    memory by the React app. It is short-lived and dies with the tab.
  * the **refresh** token goes into an httpOnly cookie. JavaScript cannot read
    it, so a script on the page cannot steal it; the browser attaches it only to
    requests to this site, and only the refresh endpoint ever looks at it.

That means the API and the site have to be same-origin, or the cookie is not sent
at all. The Vite dev server already proxies /api, and the deployment notes in the
README say to put both behind one hostname.
"""

from django.conf import settings

COOKIE_NAME = "gabstep_refresh"
# Only this one path needs it, so nothing else on the site ever receives it --
# not a static file, not an upload, not a third-party script's fetch.
COOKIE_PATH = "/api/auth/"


def _samesite():
    """`Lax` when the site and the API share an origin, `None` when they do not.

    Same-origin is the deployment to aim for: the browser sends the cookie, no
    CORS is involved, and `Lax` keeps it off other sites' requests entirely.

    But a frontend on one host and an API on another is a normal shape too, and
    there the browser will not send a `Lax` cookie at all, so every reload would
    sign the person out. `REFRESH_COOKIE_SAMESITE=None` covers that, and the
    browser then requires `Secure`, which is why it is forced on below.
    """
    value = (getattr(settings, "REFRESH_COOKIE_SAMESITE", "") or "Lax").strip().capitalize()
    return value if value in {"Lax", "Strict", "None"} else "Lax"


def set_refresh_cookie(response, token):
    samesite = _samesite()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        # Plain HTTP is only ever allowed while developing. A cross-site cookie
        # is refused by the browser without Secure, whatever DEBUG says.
        secure=(not settings.DEBUG) or samesite == "None",
        samesite=samesite,
        path=COOKIE_PATH,
    )
    return response


def clear_refresh_cookie(response):
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, samesite=_samesite())
    return response


def read_refresh_token(request):
    """The refresh token for this request.

    The cookie is the real source. A token in the body is still accepted so a
    session open in a tab from before this change keeps working until its refresh
    expires, rather than logging everyone out on deploy.
    """
    return request.COOKIES.get(COOKIE_NAME) or (request.data or {}).get("refresh") or ""
