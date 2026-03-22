from django.urls import path
from accounts import api_views

urlpatterns = [
    path('login/', api_views.LoginView.as_view()),
    path('register/', api_views.RegisterView.as_view()),
    path('refresh/', api_views.RefreshTokenView.as_view()),
    path('profile/', api_views.ProfileView.as_view()),
]