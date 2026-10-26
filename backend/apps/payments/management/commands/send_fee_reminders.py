"""Remind payers of a pay-small-small instalment coming due.

Run once a day (a Render cron job):

    python manage.py send_fee_reminders

For each fee being paid in instalments, the next instalment gets at most three
reminders: two days before it is due, on the day, and once three days late. A
missed instalment only brings reminders; the application carries on (the
desk's rule). A day the job did not run is caught up the next time, and each
reminder is recorded on the payment so it is never sent twice.

The reminder is a line on the application's feed, emailed to whoever owns the
file: the applicant, or the agent for a student they registered (the student
is never written to).
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.applications import services
from apps.payments import plans
from apps.payments.models import Payment


def reminder_kind(days_left):
    """Which reminder is due for an instalment `days_left` days away, or None."""
    if days_left <= -3:
        return "late"
    if days_left <= 0:
        return "due"
    if days_left <= 2:
        return "before"
    return None


def reminder_text(kind, amount, due_on):
    when = f"{due_on:%d %b %Y}"
    if kind == "before":
        lead = f"Reminder: the next application fee payment of ₦{amount:,.0f} is due on {when}."
    elif kind == "due":
        lead = f"Reminder: the application fee payment of ₦{amount:,.0f} is due today ({when})."
    else:
        lead = f"The application fee payment of ₦{amount:,.0f} was due on {when} and is still outstanding."
    return f"{lead} Pay it from the dashboard; the balance can also be paid at once."


class Command(BaseCommand):
    help = "Email reminders for pay-small-small instalments coming due."

    def handle(self, *args, **options):
        today = timezone.localdate()
        sent = 0
        waiting = Payment.objects.filter(
            plan=Payment.Plan.INSTALMENTS, status=Payment.Status.PART_PAID
        ).values_list("pk", flat=True)
        for pk in waiting:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().select_related("application").get(pk=pk)
                upcoming = plans.next_instalment(payment)
                if not upcoming or not upcoming["due_on"]:
                    continue
                kind = reminder_kind((upcoming["due_on"] - today).days)
                key = f"{upcoming['number']}:{kind}"
                if kind is None or key in (payment.reminders_sent or []):
                    continue
                services.notify(
                    payment.application,
                    reminder_text(kind, upcoming["outstanding_ngn"], upcoming["due_on"]),
                    send_email=True,
                )
                payment.reminders_sent = [*(payment.reminders_sent or []), key]
                payment.save(update_fields=["reminders_sent"])
                sent += 1
        self.stdout.write(f"Sent {sent} fee reminder(s).")
