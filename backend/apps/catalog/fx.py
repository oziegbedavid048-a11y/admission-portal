"""Live exchange rates.

Rates are fetched from a public provider and cached for a few minutes. The cache
is the point: a converter that moves as you type would otherwise hammer the
provider with a request per keystroke, and rates that refresh every few minutes
are as live as a daily-published feed can meaningfully be.

If the provider cannot be reached, the stored ``OriginCountry.ngn_per_unit``
table is used instead and the response says so, so the UI can label the figures
as indicative rather than quietly showing stale numbers as if they were live.
"""

import logging
from decimal import Decimal
from urllib.error import URLError
from urllib.request import urlopen
import json

from django.core.cache import cache

logger = logging.getLogger(__name__)

PROVIDER_URL = "https://open.er-api.com/v6/latest/{base}"
CACHE_KEY = "gabstep:fx:{base}"
CACHE_SECONDS = 300
REQUEST_TIMEOUT = 8


def _from_provider(base):
    url = PROVIDER_URL.format(base=base)
    with urlopen(url, timeout=REQUEST_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if payload.get("result") != "success":
        raise ValueError(payload.get("error-type", "provider returned an error"))

    return {
        "base": payload.get("base_code", base),
        "rates": payload["rates"],
        "updated_at": payload.get("time_last_update_utc"),
        "next_update_at": payload.get("time_next_update_utc"),
        "provider": payload.get("provider", "open.er-api.com"),
        "live": True,
    }


def _from_stored_table(base):
    """Derive rates from the reference table the fee quote already uses."""
    from .models import OriginCountry

    countries = list(OriginCountry.objects.all())
    naira_per = {c.currency: Decimal(c.ngn_per_unit) for c in countries}
    naira_per.setdefault("NGN", Decimal("1"))

    base_rate = naira_per.get(base)
    if not base_rate:
        return None

    # rate(base -> target) = naira per base / naira per target
    rates = {
        currency: float((base_rate / value).quantize(Decimal("0.000001")))
        for currency, value in naira_per.items()
        if value
    }

    return {
        "base": base,
        "rates": rates,
        "updated_at": None,
        "next_update_at": None,
        "provider": "Gabstep reference table",
        "live": False,
    }


def get_rates(base="NGN", force=False):
    """Rates for one base currency, cached, with a documented fallback."""
    base = (base or "NGN").upper()
    key = CACHE_KEY.format(base=base)

    if not force:
        cached = cache.get(key)
        if cached:
            return cached

    try:
        data = _from_provider(base)
        cache.set(key, data, CACHE_SECONDS)
        return data
    except (URLError, ValueError, KeyError, TimeoutError, OSError) as error:
        logger.warning("Live FX lookup for %s failed: %s", base, error)

    fallback = _from_stored_table(base)
    if fallback:
        # Cached briefly too, so a provider outage does not turn every keystroke
        # into another failed outbound request.
        cache.set(key, fallback, 60)
        return fallback

    empty = {
        "base": base,
        "rates": {},
        "updated_at": None,
        "next_update_at": None,
        "provider": None,
        "live": False,
    }
    # Remembered briefly as well, so a currency nobody has rates for does not
    # send every request back out to the provider.
    cache.set(key, empty, 60)
    return empty
