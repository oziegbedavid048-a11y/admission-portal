"""Verification now has two checks: the application fee and the documents.

Recomputes every file's checks and overall status from what actually happened,
so files that had personal or academic details ticked by hand read correctly.
Files the desk flagged as needing action keep that flag.
"""

from django.db import migrations
from django.utils import timezone


def recompute(apps, schema_editor):
    Application = apps.get_model("applications", "Application")
    Payment = apps.get_model("payments", "Payment")
    Document = apps.get_model("applications", "Document")

    settled = set(
        Payment.objects.filter(status__in=("paid", "waived")).values_list("application_id", flat=True)
    )
    for application in Application.objects.all().iterator():
        statuses = list(Document.objects.filter(application_id=application.pk).values_list("status", flat=True))
        payment_ok = application.pk in settled
        documents_ok = bool(statuses) and all(status == "Verified" for status in statuses)
        application.payment_verified = payment_ok
        application.documents_verified = documents_ok
        if application.verification_status != "action_required":
            if payment_ok and documents_ok:
                application.verification_status = "verified"
                application.verified_at = application.verified_at or timezone.now()
            elif payment_ok or documents_ok:
                application.verification_status = "in_review"
                application.verified_at = None
            else:
                application.verification_status = "unverified"
                application.verified_at = None
        application.save(
            update_fields=["payment_verified", "documents_verified", "verification_status", "verified_at"]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0014_agentapplication_agentapplications"),
        ("payments", "0007_payment_transfer_bank"),
    ]

    operations = [migrations.RunPython(recompute, migrations.RunPython.noop)]
