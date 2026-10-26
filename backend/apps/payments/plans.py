"""What an application fee covers and how it can be paid.

Two rules from the desk (October 2026):

* **Two schools for the price of one.** One application fee covers a 1st and a
  2nd choice school. The fee is the 1st choice school's own, exactly as when it
  is applied to alone; a 3rd choice adds 100,000 Naira. Each school still has
  its own application file; the 2nd and 3rd point to the 1st (`fee_parent`), and
  the 1st holds the one Payment for all of them.

* **Pay small small.** Instead of paying in full, the payer can pay a 100,000
  deposit now and the rest in two equal weekly instalments (50,000 and 50,000
  on a 200,000 fee; 100,000 and 100,000 with a 3rd school). The balance can be cleared at any
  time. Work on the files starts once the deposit is in; the agent's commission
  waits until everything is paid. A missed instalment only brings reminders.

Everything here is a pure calculation over the payment and its applications;
moving money is settlement.py's job.
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from apps.applications.constants import (
    EXTRA_SCHOOL_FEE_NGN,
    INSTALMENT_COUNT,
    INSTALMENT_DEPOSIT_NGN,
    INSTALMENT_GAP_DAYS,
    SCHOOLS_INCLUDED_IN_FEE,
)

NAIRA = Decimal("0.01")


def schools_on_fee(primary):
    """The applications one fee pays for: the 1st choice, then the others in order."""
    covered = sorted(primary.covered_applications.all(), key=lambda app: (app.choice_order, app.pk))
    return [primary, *covered]


def _fee_free(application):
    institution = application.institution
    return application.is_custom_course or institution is None or institution.is_fee_free


def pricing_application(primary):
    """The school whose fee is charged: the 1st choice, or None if nothing is owed.

    A fee-free 1st choice with fee-charging 2nd or 3rd choices is priced at the
    dearest of those, so a free school first can never make the others free.
    """
    if not _fee_free(primary):
        return primary
    paying = [app for app in schools_on_fee(primary)[1:] if not _fee_free(app)]
    if not paying:
        return None
    return max(paying, key=lambda app: app.institution.application_fee_ngn)


def extra_fee_ngn(primary):
    """What schools beyond the 2nd add, in Naira."""
    extra = max(0, len(schools_on_fee(primary)) - SCHOOLS_INCLUDED_IN_FEE)
    return (EXTRA_SCHOOL_FEE_NGN * extra).quantize(NAIRA)


def plan_total_ngn(primary):
    """The whole application fee for this 1st choice and the schools it covers."""
    pricing = pricing_application(primary)
    if pricing is None:
        return Decimal("0.00")
    return (pricing.institution.application_fee_ngn + extra_fee_ngn(primary)).quantize(NAIRA)


def instalment_amounts(total_ngn):
    """[deposit, second, third] for a fee of `total_ngn`; one amount if it is too small to split."""
    total = Decimal(total_ngn)
    if total <= INSTALMENT_DEPOSIT_NGN:
        return [total.quantize(NAIRA)]
    rest = total - INSTALMENT_DEPOSIT_NGN
    parts = INSTALMENT_COUNT - 1
    each = (rest / parts).quantize(NAIRA, rounding=ROUND_HALF_UP)
    amounts = [INSTALMENT_DEPOSIT_NGN] + [each] * (parts - 1)
    amounts.append(total - sum(amounts))  # the last one absorbs any rounding
    return [amount.quantize(NAIRA) for amount in amounts]


def schedule(payment):
    """Each instalment of a pay-small-small fee: number, amount, due date, paid.

    The deposit is due at once; each later instalment falls due a further week
    after the deposit landed (no date until then). Paid is worked out from how
    much has come in, so paying the balance early marks every instalment paid.
    """
    rows = []
    covered = Decimal(payment.paid_ngn or 0)
    running = Decimal("0")
    start = payment.deposit_paid_at
    for number, amount in enumerate(instalment_amounts(payment.amount_ngn), start=1):
        running += amount
        due = None
        if number > 1 and start is not None:
            due = (start + timedelta(days=INSTALMENT_GAP_DAYS * (number - 1))).date()
        rows.append(
            {
                "number": number,
                "amount_ngn": amount,
                "due_on": due,
                "paid": covered >= running,
                # Partly covered by an earlier, larger payment: only this much left.
                "outstanding_ngn": max(Decimal("0.00"), min(amount, running - covered)),
            }
        )
    return rows


def next_instalment(payment):
    """The first instalment not yet fully paid, or None."""
    return next((row for row in schedule(payment) if not row["paid"]), None)


def charge_for(payment, pay="next"):
    """(kind, amount in Naira) the payer is asked for now.

    `pay` is "next" (the next instalment, or the whole fee on a full plan) or
    "balance" (everything still owed). Returns None when nothing is owed.
    """
    from .models import PaymentCharge

    balance = payment.balance_ngn
    if balance <= 0:
        return None
    if payment.plan != payment.Plan.INSTALMENTS:
        return PaymentCharge.Kind.FULL, balance
    if pay == "balance":
        return PaymentCharge.Kind.BALANCE, balance
    row = next_instalment(payment)
    if row is None:
        return None
    kind = PaymentCharge.Kind.DEPOSIT if row["number"] == 1 else PaymentCharge.Kind.INSTALMENT
    return kind, row["outstanding_ngn"]


def plan_summary(payment):
    """How a fee stands, for the portals: the plan, what is paid, what is next."""
    if payment is None:
        return None
    summary = {
        "plan": payment.plan,
        "total_ngn": payment.amount_ngn,
        "paid_ngn": payment.paid_ngn,
        "balance_ngn": payment.balance_ngn,
        "instalments": [],
        "next": None,
    }
    if payment.plan == payment.Plan.INSTALMENTS:
        rows = schedule(payment)
        summary["instalments"] = rows
        upcoming = next((row for row in rows if not row["paid"]), None)
        if upcoming is not None:
            summary["next"] = {
                "number": upcoming["number"],
                "amount_ngn": upcoming["outstanding_ngn"],
                "due_on": upcoming["due_on"],
            }
    return summary
