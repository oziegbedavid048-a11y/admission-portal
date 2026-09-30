from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    label = "catalog"
    verbose_name = "Courses & countries"

    def ready(self):
        # Any change to the catalogue makes its cached answers stale.
        from django.db.models.signals import post_delete, post_save

        from .models import DestinationCountry, Institution, OriginCountry, Program
        from .views import bump_catalog_version

        for model in (DestinationCountry, Institution, OriginCountry, Program):
            post_save.connect(bump_catalog_version, sender=model, weak=False, dispatch_uid=f"catalog-cache-save-{model.__name__}")
            post_delete.connect(bump_catalog_version, sender=model, weak=False, dispatch_uid=f"catalog-cache-del-{model.__name__}")
