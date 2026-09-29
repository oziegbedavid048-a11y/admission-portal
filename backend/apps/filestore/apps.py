from django.apps import AppConfig


class FilestoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.filestore"
    label = "filestore"
    verbose_name = "Stored files"
