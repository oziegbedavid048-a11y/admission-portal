"""Money and pipeline constants shared across the applications app."""

from decimal import Decimal

# The application fee never changes: it is always this amount of Naira, shown
# to the applicant converted into their own currency.
APPLICATION_FEE_NGN = Decimal("200000")

# One application fee covers up to two schools (a 1st and a 2nd choice). The
# fee is the 1st choice school's own (in its currency, charged in Naira, never
# below its Naira minimum); a 3rd choice school adds EXTRA_SCHOOL_FEE_NGN on top
# (David's rule, October 2026).
SCHOOLS_INCLUDED_IN_FEE = 2
MAX_SCHOOLS_PER_FEE = 3
EXTRA_SCHOOL_FEE_NGN = Decimal("100000")

# "Pay small small": a deposit now, then the rest in two equal weekly
# instalments. A 200,000 fee is 100,000 now, 50,000 a week later and 50,000 a
# week after; with a 3rd school (300,000) it is 100,000, 100,000 and 100,000.
INSTALMENT_DEPOSIT_NGN = Decimal("100000")
INSTALMENT_COUNT = 3
INSTALMENT_GAP_DAYS = 7

# Paystack's own charge on a Nigerian card transaction, published at
# paystack.com/pricing: 1.5% plus a flat fee, with the flat part waived on small
# transactions and the whole thing capped. Every value is overridable from the
# environment, because a negotiated rate is a normal thing to have.
#
# This is denominated in Naira because that is what is actually charged. The old
# PROCESSING_FEE was a flat 3.50 in whatever currency the applicant was quoted
# in, which was added to the total they were shown and then never collected: the
# gateway was only ever asked for the application fee. Anything the applicant is
# shown has to be what the card is debited.
PAYSTACK_FEE_PERCENT = Decimal("1.5")
PAYSTACK_FEE_FLAT_NGN = Decimal("100")
PAYSTACK_FEE_FLAT_WAIVED_UNDER_NGN = Decimal("2500")
PAYSTACK_FEE_CAP_NGN = Decimal("2000")

# Commission an agent earns per student, per milestone:
#   * registration: when the student's application fee is confirmed,
#   * visa: when the visa desk confirms the visa support is done.
AGENT_REGISTRATION_COMMISSION_NGN = Decimal("30000")
AGENT_VISA_COMMISSION_NGN = Decimal("50000")
AGENT_COMMISSION_BY_KIND = {
    "registration": AGENT_REGISTRATION_COMMISSION_NGN,
    "visa": AGENT_VISA_COMMISSION_NGN,
}
# Kept for the model field default; the registration amount.
AGENT_COMMISSION_PER_MILESTONE = AGENT_REGISTRATION_COMMISSION_NGN

# A sales manager earns this once per student, the moment one of their agents
# registers that student. It sits on top of the agent's own commission rather
# than coming out of it: the agent is paid the same whether or not they report
# to a sales manager.
SUPERVISOR_BONUS_NGN = Decimal("2000")

# Smallest payout a sales manager can request. The same floor as an agent's,
# for the same reason: a transfer costs the same to process whatever its size.
MIN_SUPERVISOR_WITHDRAWAL_NGN = Decimal("100000")

# Smallest payout an agent can request. Each transfer costs the same to
# process whatever its size, so a floor keeps the fee proportionate and
# stops the payout run filling with trivial amounts.
MIN_WITHDRAWAL_NGN = Decimal("100000")

DEFAULT_STAGES = [
    {
        "name": "Submitted & payment confirmed",
        "note": "Application verified.",
        "eta": "Done",
    },
    {
        "name": "Document verification",
        "note": "Your documents are with the review desk.",
        "eta": "Within 48 hours",
    },
    {
        "name": "Institution review",
        "note": "Queued with the institution.",
        "eta": "Est. 5-7 days",
    },
    {
        "name": "Offer letter decision",
        "note": "Awaiting the admissions decision.",
        "eta": "Est. 2-4 weeks",
    },
    {
        "name": "Visa guidance & enrolment",
        "note": "Handled by the visa desk.",
        "eta": "Post offer",
    },
]
