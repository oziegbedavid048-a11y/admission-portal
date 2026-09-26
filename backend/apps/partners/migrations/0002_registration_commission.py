"""Rename the first commission from "admission" to "registration".

It is no longer earned when a student is admitted; it is earned the moment the
application fee is paid. Both the wallet column and the existing commission rows
move with it, so historical earnings still add up to the same total.
"""

from django.db import migrations, models


def admission_to_registration(apps, schema_editor):
    apps.get_model("partners", "Commission").objects.filter(kind="admission").update(
        kind="registration"
    )


def registration_to_admission(apps, schema_editor):
    apps.get_model("partners", "Commission").objects.filter(kind="registration").update(
        kind="admission"
    )


class Migration(migrations.Migration):
    dependencies = [("partners", "0001_initial")]

    operations = [
        migrations.RenameField(
            model_name="wallet",
            old_name="admission_commission_total",
            new_name="registration_commission_total",
        ),
        migrations.AlterField(
            model_name="commission",
            name="kind",
            field=models.CharField(
                choices=[
                    ("registration", "Student registered and fee paid"),
                    ("visa", "Visa verified"),
                ],
                max_length=12,
            ),
        ),
        migrations.RunPython(admission_to_registration, registration_to_admission),
    ]
