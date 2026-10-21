# Gives bank_code a database-level default of '' on PostgreSQL.
#
# Migration 0016 reached the live database before the code that declares the
# new fields was deployed, so the running site inserted agents without
# bank_code and Postgres refused (NotNullViolation): agent sign-up failed from
# 15 to 19 October 2026. The deployed model now declares the field, which is the
# real fix; this default is a second line of defence, and it is already applied
# on the live database, so the migration is kept to match it.
#
# PostgreSQL only: SQLite (the test database) has no ALTER COLUMN ... SET DEFAULT.

from django.db import migrations

TABLES = ("partners_agentprofile", "partners_supervisorprofile")


def set_default(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(f"ALTER TABLE {table} ALTER COLUMN bank_code SET DEFAULT ''")


def drop_default(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(f"ALTER TABLE {table} ALTER COLUMN bank_code DROP DEFAULT")


class Migration(migrations.Migration):

    dependencies = [
        ("partners", "0016_paystack_payouts"),
    ]

    operations = [
        migrations.RunPython(set_default, drop_default),
    ]
