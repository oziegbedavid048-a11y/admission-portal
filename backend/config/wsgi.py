import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
try:
    from django.core.management import call_command
    call_command("migrate", interactive=False)
except Exception as _migrate_exc:
    import logging
    logging.getLogger(__name__).warning("WSGI auto-migration notice: %s", _migrate_exc)

