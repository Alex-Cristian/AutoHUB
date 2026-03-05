from django.apps import AppConfig


class BookingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bookings'
    verbose_name = 'Programări'

    def ready(self):
        # Register signals (create notifications on booking events)
        from . import signals  # noqa: F401
