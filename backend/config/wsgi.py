import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

logger = logging.getLogger(__name__)

# Migrations run once at start-up as a safety net, in case a deploy's build
# step did not run them (build.sh does). With several gunicorn workers each
# would run them at the same moment and could trip over one another, so on
# PostgreSQL they take a database lock first: one worker migrates, the others
# wait and then find nothing left to do.
MIGRATE_LOCK_ID = 7_302_116_501


def _migrate_once():
    from django.core.management import call_command
    from django.db import connection

    if connection.vendor != "postgresql":
        call_command("migrate", interactive=False, verbosity=0)
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [MIGRATE_LOCK_ID])
        try:
            call_command("migrate", interactive=False, verbosity=0)
        finally:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [MIGRATE_LOCK_ID])


try:
    _migrate_once()
except Exception as exc:  # noqa: BLE001 - a failed safety net must not stop the site
    logger.warning("Start-up migration did not run: %s", exc)
