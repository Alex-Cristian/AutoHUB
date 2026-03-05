from django.apps import AppConfig
<<<<<<< HEAD
=======


>>>>>>> origin/main
class BookingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bookings'
    verbose_name = 'Programări'
<<<<<<< HEAD
=======

    def ready(self):
        # Register signals (create notifications on booking events)
        from . import signals  # noqa: F401
>>>>>>> origin/main
