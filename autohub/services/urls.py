from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    path('', views.service_list, name='list'),
    path('categorii/', views.category_list, name='categories'),
    path('inregistrare-service/', views.service_register, name='register_service'),
    path('inregistrare-firma/', views.service_register_public, name='register_public'),
    path('dashboard/', views.service_dashboard, name='dashboard'),
    path('dashboard/notificari/', views.service_notifications, name='notifications'),
    path('dashboard/notificari/<int:pk>/citit/', views.notification_mark_read, name='notification_read'),
    path('dashboard/programari/<int:pk>/accepta/', views.booking_accept, name='booking_accept'),
    path('dashboard/programari/<int:pk>/respinge/', views.booking_reject, name='booking_reject'),
    path('dashboard/service/<int:pk>/', views.service_profile_manage, name='manage_profile'),
    path('dashboard/garaje/<int:pk>/sterge/', views.garage_delete, name='garage_delete'),
    path('dashboard/poze/<int:pk>/sterge/', views.gallery_image_delete, name='gallery_image_delete'),
    path('verificare/', views.verification_list, name='verification_list'),
    path('verificare/<int:pk>/', views.verification_detail, name='verification_detail'),
    path('verificare/<int:pk>/aproba/', views.verification_approve, name='verification_approve'),
    path('verificare/<int:pk>/respinge/', views.verification_reject, name='verification_reject'),
    path('<slug:slug>/recenzie/', views.review_create, name='review_create'),
    path('<slug:slug>/', views.service_detail, name='detail'),
    path('<slug:slug>/favorit/', views.toggle_favorite, name='toggle_favorite'),
]
