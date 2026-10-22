from django.apps import AppConfig


class FeesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.fees"

    def ready(self):
        from . import signals  # noqa: F401  (registers the new-allocation listener)
    label = "fees"
    verbose_name = "Fees"
