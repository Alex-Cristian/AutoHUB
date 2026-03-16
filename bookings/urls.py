from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('programare/<slug:slug>/', views.booking_create, name='create'),
    path('programare/<slug:slug>/durata/', views.booking_duration_estimate, name='duration_estimate'),
    path('programare/<slug:slug>/sloturi/', views.garage_slots, name='garage_slots'),
    path('confirmare/<int:pk>/', views.booking_success, name='success'),
    path('programarile-mele/', views.my_bookings, name='my_bookings'),
    path('atasamente/<int:pk>/sterge/', views.attachment_delete, name='attachment_delete'),
    path('programare/<slug:slug>/garaje/', views.garaje_disponibile, name='garaje_disponibile'),
]