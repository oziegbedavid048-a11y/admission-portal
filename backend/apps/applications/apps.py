from django.apps import AppConfig


class ApplicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.applications"
    label = "applications"
    verbose_name = "Applications"

    def ready(self):
        # Every upload is compressed before it is stored. See compression.py.
        from . import compression

        compression.connect()
