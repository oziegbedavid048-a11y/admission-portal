"""Normalise the stored payment status to lower case.

`PAID` was the only choice stored with a capital letter — "Paid" beside
"pending", "waived" and "failed" — and eight places across the backend compared
against that exact string. One of them was a dict literal keyed on it, so
changing the value later would have silently reclassified every settled payment
as pending without any error to notice.
"""

from django.db import migrations


def to_lower(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    Payment.objects.filter(status="Paid").update(status="paid")


def to_mixed(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    Payment.objects.filter(status="paid").update(status="Paid")


class Migration(migrations.Migration):
    dependencies = [("payments", "0002_alter_payment_options")]

    operations = [
        migrations.RunPython(to_lower, to_mixed),
    ]
