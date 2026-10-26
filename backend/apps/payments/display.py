"""The currency a student sees their application fee in.

Every fee screen (the applicant's application and dashboard, the agent's fee
step for a student, the student's payment link page) shows amounts in the
student's own country's currency only: Naira for a student from Nigeria,
cedis for one from Ghana, and so on. The country is the one on the
application (the student's country of origin), whether the applicant filed it
or an agent did.

The fee is still charged in Naira (Paystack's checkout shows that figure); the
screens convert it at today's rate, the same rate agent wallets use: the live
rate, or the admin's Exchange rates table when the provider is down. When no
rate is on file for a currency, Naira is shown rather than a guess.

The portals receive the currency and the rate and convert every amount the
same way, so a total and its instalments always agree.
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

NAIRA = {"code": "NGN", "symbol": "₦", "ngn_per_unit": "1"}


def student_currency(country):
    """{"code", "symbol", "ngn_per_unit"} for an OriginCountry (or None)."""
    from apps.partners.currency import naira_per_unit

    code = ((getattr(country, "currency", "") or "NGN").strip().upper()) if country else "NGN"
    if code == "NGN":
        return dict(NAIRA)
    try:
        rate = Decimal(naira_per_unit(code))
    except (ValueError, ArithmeticError):
        logger.warning("No exchange rate for %s; fees are shown in Naira.", code)
        return dict(NAIRA)
    if rate <= 0:
        return dict(NAIRA)
    return {
        "code": code,
        "symbol": (getattr(country, "symbol", "") or code).strip(),
        "ngn_per_unit": str(rate),
    }


def for_application(application):
    """The currency this application's student sees the fee in."""
    return student_currency(getattr(application, "origin_country", None))


def format_amount(ngn, currency):
    """A Naira amount written in `currency` (from student_currency), as the
    portals write it: "₦50,000", "GH₵500", "D 1,250.50"."""
    value = Decimal(ngn or 0)
    rate = Decimal(currency.get("ngn_per_unit") or "1") if currency else Decimal("1")
    amount = (value / rate).quantize(Decimal("0.01")) if rate else value
    text = f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,.2f}"
    symbol = (currency or {}).get("symbol") or (currency or {}).get("code") or "₦"
    return f"{symbol} {text}" if symbol.isalpha() else f"{symbol}{text}"
