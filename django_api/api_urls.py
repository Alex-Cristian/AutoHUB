# autohub/api_urls.py
# Copiaza in AutoHUB-main/autohub/api_urls.py

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.api_views import api_login, api_register, api_profile, api_cars, api_car_detail, api_car_expiry, api_my_bookings
from services.api_views_extended import api_categories, api_service_detail, api_favorites, api_toggle_favorite, api_add_review, api_owner_dashboard, api_owner_bookings, api_owner_booking_update
from services.api_views import services_api, services_nearby

urlpatterns = [
    path('auth/login/',    api_login,    name='api_login'),
    path('auth/register/', api_register, name='api_register'),
    path('auth/refresh/',  TokenRefreshView.as_view(), name='api_token_refresh'),
    path('profile/',       api_profile,  name='api_profile'),
    path('cars/',          api_cars,     name='api_cars'),
    path('cars/<int:pk>/', api_car_detail, name='api_car_detail'),
    path('cars/<int:pk>/expiry/', api_car_expiry, name='api_car_expiry'),
    path('my-bookings/',   api_my_bookings, name='api_my_bookings'),
    path('services/',      services_api, name='api_services'),
    path('services/nearby/', services_nearby, name='api_services_nearby'),
    path('services/<slug:slug>/', api_service_detail, name='api_service_detail'),
    path('services/<slug:slug>/favorite/', api_toggle_favorite, name='api_toggle_favorite'),
    path('services/<slug:slug>/review/', api_add_review, name='api_add_review'),
    path('categories/',    api_categories, name='api_categories'),
    path('favorites/',     api_favorites,  name='api_favorites'),
    path('owner/dashboard/', api_owner_dashboard, name='api_owner_dashboard'),
    path('owner/bookings/', api_owner_bookings, name='api_owner_bookings'),
    path('owner/bookings/<int:pk>/', api_owner_booking_update, name='api_owner_booking_update'),
]
