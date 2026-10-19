# Hand-written migration -- fixes the NOT NULL violation that crashed agent
# registration.  Migration 0016 added bank_code as blank=True but on some
# database engines the column was created WITHOUT a default expression, so
# inserting a row without explicitly providing bank_code raises:
#
#   psycopg.errors.NotNullViolation: null value in column "bank_code" of
#   relation "partners_agentprofile" violates not-null constraint
#
# This migration sets the server-side DEFAULT to '' so any INSERT that omits
# the column succeeds.  The serializer now also passes bank_code='' explicitly,
# but this migration is belt-and-braces insurance for the database layer.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("partners", "0016_paystack_payouts"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE partners_agentprofile ALTER COLUMN bank_code SET DEFAULT '';",
                "ALTER TABLE partners_supervisorprofile ALTER COLUMN bank_code SET DEFAULT '';",
            ],
            reverse_sql=[
                "ALTER TABLE partners_agentprofile ALTER COLUMN bank_code DROP DEFAULT;",
                "ALTER TABLE partners_supervisorprofile ALTER COLUMN bank_code DROP DEFAULT;",
            ],
        ),
    ]
