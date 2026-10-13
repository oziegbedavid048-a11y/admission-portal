from django.apps import AppConfig


class TestAccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.testaccounts"
    label = "testaccounts"
    verbose_name = "Test accounts"
