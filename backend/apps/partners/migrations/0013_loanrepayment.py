from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


def record_earlier_repayments(apps, schema_editor):
    """Repayments made before this table existed are only a total on the
    wallet. Each becomes one row, dated when the wallet last changed, so the
    history still adds up to what was taken from the balance."""
    Wallet = apps.get_model("partners", "Wallet")
    LoanRepayment = apps.get_model("partners", "LoanRepayment")
    for wallet in Wallet.objects.filter(loan_repaid_total__gt=Decimal("0.00")):
        row = LoanRepayment.objects.create(agent_id=wallet.agent_id, amount=wallet.loan_repaid_total)
        LoanRepayment.objects.filter(pk=row.pk).update(created_at=wallet.updated_at)


class Migration(migrations.Migration):

    dependencies = [
        ("partners", "0012_wallet_loan_repaid_total"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoanRepayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="loan_repayments",
                        to="partners.agentprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "ads funding repayment",
                "verbose_name_plural": "ads funding repayments",
                "ordering": ("-created_at",),
            },
        ),
        migrations.RunPython(record_earlier_repayments, migrations.RunPython.noop),
    ]
