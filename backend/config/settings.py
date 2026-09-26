"""Django settings for the Gabstep visa application backend."""

from datetime import timedelta
from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# Debug defaults OFF. A deployment that forgets to set it gets the safe
# behaviour, not stack traces with settings in them; a developer sets
# DJANGO_DEBUG=True in .env once and never thinks about it again.
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        # No fallback. A shared default key means anyone holding this source can
        # forge a session cookie or a password-reset token for every deployment
        # that never overrode it.
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set. Generate one with: python -c "
            "'from django.core.management.utils import get_random_secret_key "
            "as k; print(k())'"
        )
    # Development only, and regenerated on every start so it can never quietly
    # become the key something depends on.
    SECRET_KEY = get_random_secret_key()

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")

# Render sets this to the service's own hostname. Adding it here means a first
# deploy answers rather than returning a DisallowedHost for the one address the
# platform actually routes to.
RENDER_HOST = env("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST and RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOST)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # Local
    "apps.accounts",
    "apps.catalog",
    "apps.applications",
    "apps.partners",
    "apps.payments",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.UploadedFileHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# A DATABASE_URL of the form
#   postgres://user:pass@host:port/name?sslmode=require
# switches the project onto PostgreSQL without any other change. The query string
# matters: a managed provider almost always requires TLS, and the old version of
# this block dropped it, so a connection that was supposed to be encrypted would
# quietly fall back to plaintext or be refused outright.
DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    from urllib.parse import parse_qsl, unquote, urlparse

    parsed = urlparse(DATABASE_URL)
    options = {key: value for key, value in parse_qsl(parsed.query)}
    # A managed Postgres is TLS-only in practice, so require it unless the URL
    # deliberately says otherwise.
    options.setdefault("sslmode", "require")

    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "OPTIONS": options,
        # Reuse a connection for ten minutes rather than opening one per request.
        # The pooler in front of a managed database charges for connections, and
        # the handshake is the slowest part of a short request.
        "CONN_MAX_AGE": int(env("CONN_MAX_AGE", "600")),
        "CONN_HEALTH_CHECKS": True,
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    # Nothing here was rate limited, which made the sign-in endpoint a free
    # password oracle and the email-availability endpoint a free way to list who
    # holds an account. The scopes below are applied per view; `anon` and `user`
    # are the floor for everything else.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", "60/min"),
        "user": env("THROTTLE_USER", "240/min"),
        # A person signing in mistypes a password twice, not twenty times.
        "login": env("THROTTLE_LOGIN", "8/min"),
        "register": env("THROTTLE_REGISTER", "5/hour"),
        # Checking whether an address is taken is a lookup against every account
        # on the platform, so it is the tightest of the lot.
        "email_check": env("THROTTLE_EMAIL_CHECK", "20/hour"),
        # Money leaving the platform, and a file being uploaded, are both worth
        # slowing down well below what a person could ever need.
        "money": env("THROTTLE_MONEY", "12/hour"),
        "upload": env("THROTTLE_UPLOAD", "60/hour"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("ACCESS_TOKEN_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("REFRESH_TOKEN_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Gabstep Visa Application API",
    "DESCRIPTION": "Applicant, partner-agent and admissions endpoints.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

def _clean_origin(raw_origin):
    raw_origin = raw_origin.strip()
    if not raw_origin:
        return ""
    if "://" in raw_origin:
        from urllib.parse import urlparse
        p = urlparse(raw_origin)
        return f"{p.scheme}://{p.netloc}"
    return raw_origin

_raw_cors = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
CORS_ALLOWED_ORIGINS = [_clean_origin(o) for o in _raw_cors if _clean_origin(o)]
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", False)

# The API is authenticated with a bearer token in the Authorization header, never
# with a cookie, so the browser has no credentials to attach to a cross-origin
# call. Allowing them would widen what a hostile page could ask the browser to
# send on a signed-in person's behalf, and buy nothing.
CORS_ALLOW_CREDENTIALS = False
# The admin is a session-cookie app served from this same origin, so it does need
# its own trusted origins. Those are the site's own addresses, not the API's
# callers, which is why this is its own setting rather than a copy of the CORS
# list.
_raw_csrf = env_list("CSRF_TRUSTED_ORIGINS", ",".join(CORS_ALLOWED_ORIGINS))
CSRF_TRUSTED_ORIGINS = [_clean_origin(o) for o in _raw_csrf if _clean_origin(o)]

# File upload ceilings. The wizard accepts PDFs and scans; anything larger than
# this is refused before it reaches a serializer.
MAX_UPLOAD_SIZE_MB = int(env("MAX_UPLOAD_SIZE_MB", "10"))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# DATABASE_URL carries the database password and matches none of the names Django
# masks by default, so the filter is extended rather than relied on. See
# config/reporting.py.
DEFAULT_EXCEPTION_REPORTER_FILTER = "config.reporting.GabstepReporterFilter"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ── Email / SMTP (cPanel) ─────────────────────────────────────────
EMAIL_HOST = env("EMAIL_HOST", "mail.gabstep.com")
EMAIL_PORT = int(env("EMAIL_PORT", "465"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "support@gabstep.com")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
default_email_backend = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_PASSWORD
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_BACKEND = env("EMAIL_BACKEND", default_email_backend)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", True)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "15"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Gabstep <support@gabstep.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ── Payments ──────────────────────────────────────────────────────
# With a secret key set, the applicant pays online and the provider posts to
# /api/payments/webhook/paystack/, which is the only thing that can settle a
# payment without a human. With no key the platform runs in transfer mode: the
# fee is recorded as outstanding and the admissions desk confirms the transfer
# in the admin. Both credit the agent's commission; nothing else does.
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY")
PAYSTACK_PUBLIC_KEY = env("PAYSTACK_PUBLIC_KEY")

# Paystack's own charge, from paystack.com/pricing. Overridable because a
# negotiated rate is normal. The applicant is shown this on top of the fee and the
# card is debited the sum, so the number on screen is the number on the statement.
PAYSTACK_FEE_PERCENT = env("PAYSTACK_FEE_PERCENT", "1.5")
PAYSTACK_FEE_FLAT_NGN = env("PAYSTACK_FEE_FLAT_NGN", "100")
PAYSTACK_FEE_FLAT_WAIVED_UNDER_NGN = env("PAYSTACK_FEE_FLAT_WAIVED_UNDER_NGN", "2500")
PAYSTACK_FEE_CAP_NGN = env("PAYSTACK_FEE_CAP_NGN", "2000")

# Optional allowlist for webhook callers, checked before the signature as defence
# in depth. Leave empty behind a proxy that does not pass the original address
# through, which is the common case on a managed host: the signature is what
# actually authenticates a webhook, not the address it came from.
PAYSTACK_WEBHOOK_IPS = env_list("PAYSTACK_WEBHOOK_IPS", "")

# The account an applicant transfers the fee to when no online provider is
# configured. These were hardcoded into the checkout dialog as placeholder
# numbers, which is a fee paid into an account nobody owns; they belong in the
# environment so they can be the real ones without touching the source.
PAYOUT_BANK_NAME = env("PAYOUT_BANK_NAME")
PAYOUT_BANK_ACCOUNT = env("PAYOUT_BANK_ACCOUNT")
PAYOUT_BANK_BENEFICIARY = env("PAYOUT_BANK_BENEFICIARY")

# Where the links in an email point. Every "Sign in" button in a message is
# built from this, so leaving it at the development default sends real
# recipients to a localhost address that only works on this machine.
FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173")
