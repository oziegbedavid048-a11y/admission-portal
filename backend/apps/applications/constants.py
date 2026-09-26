"""Money and pipeline constants shared across the applications app."""

from decimal import Decimal

# The application fee never changes: it is always this amount of Naira, shown
# to the applicant converted into their own currency.
APPLICATION_FEE_NGN = Decimal("200000")

# Gateway processing fee, charged only when the institution fee is not waived.
PROCESSING_FEE = Decimal("3.50")

# Commission an agent earns per student, per milestone.
AGENT_COMMISSION_PER_MILESTONE = Decimal("30000")

# A sales manager earns this once per student, the moment one of their agents
# registers that student. It sits on top of the agent's own commission rather
# than coming out of it: the agent is paid the same whether or not they report
# to a sales manager.
SUPERVISOR_BONUS_NGN = Decimal("2000")

# Smallest payout a sales manager can request. The same floor as an agent's,
# for the same reason: a transfer costs the same to process whatever its size.
MIN_SUPERVISOR_WITHDRAWAL_NGN = Decimal("100000")

# Share of a withdrawal that repays an outstanding ad-funding loan.
LOAN_REPAYMENT_RATE = Decimal("0.10")

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
