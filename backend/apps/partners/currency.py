"""The currency an agent's wallet is kept in.

Agents in Nigeria earn and are shown Naira. An agent anywhere else is shown
their own country's currency: every commission is worked out in Naira (the
amounts are set in Naira), converted at the exchange rate of the moment it is
credited, and stored in the agent's currency at that rate, so a later move in
the rate never changes money already in the wallet.

The country-to-currency table is the "Exchange rates" list in the admin
(catalog.OriginCountry). A country not on it falls back to Naira, so a missing
row never stops a commission being paid.
"""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

NAIRA = "NGN"
NAIRA_SYMBOL = "₦"
CENT = Decimal("0.01")


def currency_for_country(country_name):
    """(currency code, symbol) for an agent's country; Naira when unknown."""
    from apps.catalog.models import OriginCountry

    name = (country_name or "").strip()
    if not name:
        return NAIRA, NAIRA_SYMBOL
    row = OriginCountry.objects.filter(name__iexact=name).only("currency", "symbol").first()
    if row is None or not row.currency:
        return NAIRA, NAIRA_SYMBOL
    currency = row.currency.strip().upper()
    if currency == NAIRA:
        return NAIRA, NAIRA_SYMBOL
    return currency, (row.symbol or currency).strip()


def symbol_for(currency):
    """The symbol a currency is written with, from the same table."""
    from apps.catalog.models import OriginCountry

    currency = (currency or NAIRA).upper()
    if currency == NAIRA:
        return NAIRA_SYMBOL
    row = OriginCountry.objects.filter(currency__iexact=currency).only("symbol").first()
    return (row.symbol if row and row.symbol else currency).strip()


def naira_per_unit(currency):
    """How many Naira one unit of `currency` is worth right now.

    The live rate (cached for a few minutes; see catalog/fx.py) when the
    provider answers, otherwise the reference rate in the admin's table.
    """
    from apps.catalog.fx import get_rates
    from apps.catalog.models import OriginCountry

    currency = (currency or NAIRA).upper()
    if currency == NAIRA:
        return Decimal("1")

    rate = (get_rates(NAIRA).get("rates") or {}).get(currency)
    if rate:
        units_per_naira = Decimal(str(rate))
        if units_per_naira > 0:
            return (Decimal("1") / units_per_naira).quantize(Decimal("0.000001"))

    row = OriginCountry.objects.filter(currency__iexact=currency).only("ngn_per_unit").first()
    if row is not None and row.ngn_per_unit:
        return Decimal(row.ngn_per_unit)
    raise ValueError(f"No exchange rate on file for {currency}.")


def from_naira(amount_ngn, currency):
    """(amount in `currency`, Naira per unit used). Rounded to the cent."""
    currency = (currency or NAIRA).upper()
    amount_ngn = Decimal(amount_ngn)
    if currency == NAIRA:
        return amount_ngn.quantize(CENT), Decimal("1")
    rate = naira_per_unit(currency)
    return (amount_ngn / rate).quantize(CENT, rounding=ROUND_HALF_UP), rate


def threshold_from_naira(amount_ngn, currency):
    """A limit set in Naira (a minimum withdrawal, an Ads funding range), in
    `currency` at today's rate, rounded up to a whole unit so it reads cleanly."""
    converted, _ = from_naira(amount_ngn, currency)
    if (currency or NAIRA).upper() == NAIRA:
        return converted
    return converted.quantize(Decimal("1"), rounding=ROUND_CEILING)


def money(amount, currency=NAIRA, symbol=None):
    """An amount as people read it: "₦30,000", "KSh 2,450.75"."""
    currency = (currency or NAIRA).upper()
    symbol = symbol or symbol_for(currency)
    value = Decimal(amount or 0)
    if value == value.to_integral_value():
        text = f"{value:,.0f}"
    else:
        text = f"{value:,.2f}"
    return f"{symbol}{text}" if currency == NAIRA else f"{symbol} {text}"
