from django.urls import path
from . import api_views

urlpatterns = [
    path('services/', api_views.services_api, name='api_services'),
<<<<<<< HEAD
    path('services/nearby/', api_views.services_nearby, name='api_services_nearby'),
=======
>>>>>>> origin/main
]
