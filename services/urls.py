from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    path('', views.service_list, name='list'),
    path('categorii/', views.category_list, name='categories'),
    path('inregistrare-service/', views.service_register, name='register_service'),
    path('dashboard/', views.service_dashboard, name='dashboard'),
    path('dashboard/notificari/', views.service_notifications, name='notifications'),
    path('dashboard/notificari/<int:pk>/citit/', views.notification_mark_read, name='notification_read'),
    path('dashboard/programari/<int:pk>/accepta/', views.booking_accept, name='booking_accept'),
    path('dashboard/programari/<int:pk>/respinge/', views.booking_reject, name='booking_reject'),
    path('<slug:slug>/', views.service_detail, name='detail'),
    path('<slug:slug>/favorit/', views.toggle_favorite, name='toggle_favorite'),
]
