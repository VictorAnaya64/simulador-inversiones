from django.apps import AppConfig


class PortafoliosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.portafolios'
    verbose_name = 'Portafolios'

    def ready(self):
        from . import signals  # noqa: F401
