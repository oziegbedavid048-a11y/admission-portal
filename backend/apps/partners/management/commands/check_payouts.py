"""Ask Paystack about payouts still marked Sending.

Paystack normally reports each transfer on the webhook within seconds. This is
the safety net for a notice that never arrived: run it every few minutes (for
example as a Render cron job) and any payout Paystack has settled or failed is
brought up to date, with the agent's money refunded on a failure. Payouts
Paystack refused for a low company balance are also sent again (see
payouts.resend_low_balance); they can only ever be paid once.

    python manage.py check_payouts
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.partners.models import SupervisorWithdrawal, Withdrawal
from apps.partners.payouts import check, resend_low_balance


class Command(BaseCommand):
    help = "Bring payouts that are still Sending up to date with Paystack."

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than", type=int, default=2,
            help="Only payouts sent at least this many minutes ago (default 2).",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=options["older_than"])
        sending = [
            withdrawal
            for model in (Withdrawal, SupervisorWithdrawal)
            for withdrawal in model.objects.filter(
                method=Withdrawal.Method.PAYSTACK, status=Withdrawal.Status.SENDING, sent_at__lte=cutoff
            )
        ]
        changed = sum(1 for withdrawal in sending if check(withdrawal).status != Withdrawal.Status.SENDING)
        self.stdout.write(f"Checked {len(sending)} payout(s); {changed} updated.")
        # Payouts held back because the Paystack balance was low go out again
        # once it is topped up, each under its own unchanging reference.
        resent = resend_low_balance()
        self.stdout.write(f"Tried {resent} payout(s) held for a low Paystack balance again.")

        # Ads funding paid to Meta invoices: the same two jobs.
        from apps.partners import loan_payouts
        from apps.partners.models import Loan

        loans = list(Loan.objects.filter(status=Loan.Status.SENDING, sent_at__lte=cutoff))
        moved = sum(1 for loan in loans if loan_payouts.check(loan).status != Loan.Status.SENDING)
        self.stdout.write(f"Checked {len(loans)} ads funding payment(s); {moved} updated.")
        self.stdout.write(f"Tried {loan_payouts.resend_low_balance()} ads funding payment(s) held for a low balance again.")
