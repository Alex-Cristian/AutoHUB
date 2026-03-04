from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('programare/<slug:slug>/', views.booking_create, name='create'),
    path('confirmare/<int:pk>/', views.booking_success, name='success'),
    path('programarile-mele/', views.my_bookings, name='my_bookings'),
]
