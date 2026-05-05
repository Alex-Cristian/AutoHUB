from django.urls import path

from . import api_views

app_name = 'accounts_api'

urlpatterns = [
    path('register', api_views.register_api, name='register'),
    path('login', api_views.login_api, name='login'),
    path('logout', api_views.logout_api, name='logout'),
    path('me', api_views.me_api, name='me'),
    path('google', api_views.google_start_api, name='google'),
    path('google/callback', api_views.google_callback_api, name='google_callback'),
]
