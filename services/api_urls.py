from django.urls import path
from . import api_views

urlpatterns = [
    path('services/', api_views.services_api, name='api_services'),
]
