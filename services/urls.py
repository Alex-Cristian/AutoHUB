from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    path('', views.service_list, name='list'),
    path('categorii/', views.category_list, name='categories'),
    path('inregistrare-service/', views.service_register, name='register_service'),
    path('inregistrare-firma/', views.service_register_public, name='register_public'),
    path('dashboard/', views.service_dashboard, name='dashboard'),
    path('dashboard/rapoarte/', views.service_reports, name='reports'),
    path('dashboard/rapoarte/export-csv/', views.export_report_csv_view, name='export_report_csv'),
    path('dashboard/calendar/', views.service_calendar, name='calendar'),
    path('dashboard/calendar/events/', views.service_calendar_events, name='calendar_events'),
    path('dashboard/calendar/<int:pk>/update/', views.service_calendar_update_booking, name='calendar_update_booking'),
    path('dashboard/programari/', views.bookings_list, name='bookings_list'),  # ← mutat aici
    path('dashboard/mechanici/', views.mechanics_list, name='mechanics_list'),
    path('dashboard/istoric-masini/', views.service_car_history, name='car_history'),
    path('dashboard/piese/', views.parts_inventory, name='parts_inventory'),
    path('dashboard/mechanici/<int:pk>/profil/', views.mechanic_profile, name='mechanic_profile'),
    path('dashboard/service/<int:pk>/mechanici/adauga/', views.mechanic_create, name='mechanic_create'),
    path('dashboard/mechanici/<int:pk>/editeaza/', views.mechanic_update, name='mechanic_update'),
    path('dashboard/mechanici/<int:pk>/sterge/', views.mechanic_delete, name='mechanic_delete'),
    path('dashboard/service/<int:pk>/programare-noua/', views.owner_booking_create, name='owner_booking_create'),
    path('dashboard/notificari/', views.service_notifications, name='notifications'),
    path('dashboard/notificari/feed/', views.notifications_feed, name='notifications_feed'),
    path('dashboard/notificari/<int:pk>/citit/', views.notification_mark_read, name='notification_read'),
    path('dashboard/programari/<int:pk>/', views.booking_detail, name='booking_detail'),
    path('dashboard/programari/<int:pk>/print/', views.booking_print, name='booking_print'),
    path('dashboard/programari/<int:pk>/fisa-rar.pdf', views.booking_rar_pdf, name='booking_rar_pdf'),
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
    path('<slug:slug>/favorit/', views.toggle_favorite, name='toggle_favorite'),
    path('<slug:slug>/', views.service_detail, name='detail'),
]
