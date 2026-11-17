"""Give every school the code applicants see instead of its name."""

from django.db import migrations, models


def give_codes(apps, schema_editor):
    from apps.catalog.models import new_school_code

    Institution = apps.get_model("catalog", "Institution")
    taken = set()
    for school in Institution.objects.select_related("country").order_by("pk"):
        if not school.code:
            school.code = new_school_code(school.country, taken)
            school.save(update_fields=["code"])
        taken.add(school.code)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0015_landing_reviews_seed"),
    ]

    operations = [
        migrations.AddField(
            model_name="institution",
            name="code",
            field=models.CharField(blank=True, max_length=12, null=True, verbose_name="school code"),
        ),
        migrations.RunPython(give_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="institution",
            name="code",
            field=models.CharField(
                blank=True,
                help_text="Shown to applicants instead of the name until they pay, e.g. CA-418. Left blank, one is made.",
                max_length=12,
                unique=True,
                verbose_name="school code",
            ),
        ),
    ]
