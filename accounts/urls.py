from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('profil/', views.profile, name='profile'),

    # Mașinile mele
    path('masini/', views.car_list, name='cars'),
    path('masini/adauga/', views.car_create, name='car_create'),
    path('masini/<int:pk>/editeaza/', views.car_update, name='car_update'),
    path('masini/<int:pk>/sterge/', views.car_delete, name='car_delete'),
]
