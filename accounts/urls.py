from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('accepta-documente-legale/', views.accept_legal_view, name='accept_legal'),
    path('profil/', views.profile, name='profile'),
    path('scan-document/api/', views.document_scan_api, name='document_scan_api'),

    # Mașinile mele
    path('masini/', views.car_list, name='cars'),
    path('masini/adauga/', views.car_create, name='car_create'),
    path('masini/<int:pk>/editeaza/', views.car_update, name='car_update'),
    path('masini/<int:pk>/sterge/', views.car_delete, name='car_delete'),
    path('masini/<int:pk>/calendar-expirari/', views.car_expiry_calendar, name='car_calendar'),
    path('masini/<int:pk>/istoric/', views.car_service_history, name='car_history'),
    path('masini/<int:pk>/scan/', views.car_scan_document, name='car_scan'),
    path('masini/<int:pk>/scan/api/', views.car_scan_api, name='car_scan_api'),
    path('masini/<int:pk>/scan/salveaza/', views.car_scan_save, name='car_scan_save'),
]
