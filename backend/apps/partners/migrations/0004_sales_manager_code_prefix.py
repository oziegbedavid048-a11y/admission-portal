"""Move sales-manager codes from the AGT- prefix to GSA-.

AGT- was already the agent's own partner code, so two different identifiers
looked alike. Existing codes are rewritten in place, keeping their random part,
so anyone who has already been given a code only has to change three letters.
"""

from django.db import migrations, models

import apps.partners.models


def agt_to_gsa(apps, schema_editor):
    Supervisor = apps.get_model("partners", "SupervisorProfile")
    for profile in Supervisor.objects.filter(agent_code__startswith="AGT-"):
        profile.agent_code = "GSA-" + profile.agent_code[4:]
        profile.save(update_fields=["agent_code"])


def gsa_to_agt(apps, schema_editor):
    Supervisor = apps.get_model("partners", "SupervisorProfile")
    for profile in Supervisor.objects.filter(agent_code__startswith="GSA-"):
        profile.agent_code = "AGT-" + profile.agent_code[4:]
        profile.save(update_fields=["agent_code"])


class Migration(migrations.Migration):
    dependencies = [("partners", "0003_supervisorprofile_agentprofile_supervisor_and_more")]

    operations = [
        migrations.AlterModelOptions(
            name="supervisorprofile",
            options={
                "ordering": ("-created_at",),
                "verbose_name": "sales manager",
                "verbose_name_plural": "sales managers",
            },
        ),
        migrations.AlterModelOptions(
            name="supervisorbonus",
            options={
                "ordering": ("-earned_at",),
                "verbose_name": "sales manager bonus",
                "verbose_name_plural": "sales manager bonuses",
            },
        ),
        migrations.AlterField(
            model_name="supervisorprofile",
            name="agent_code",
            field=models.CharField(
                default=apps.partners.models.generate_agent_code,
                help_text="Agents enter this when they register to join this sales manager.",
                max_length=12,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="supervisorprofile",
            name="region",
            field=models.CharField(
                blank=True,
                help_text="Territory or team this sales manager covers.",
                max_length=120,
            ),
        ),
        migrations.RunPython(agt_to_gsa, gsa_to_agt),
    ]
