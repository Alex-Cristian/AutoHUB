from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('despre/', views.about, name='about'),
    path('termeni-si-conditii/', views.terms, name='terms'),
    path('politica-de-confidentialitate/', views.privacy, name='privacy'),
    path('politica-cookie/', views.cookies, name='cookies'),
]
