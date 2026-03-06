from django.urls import path

from . import views

app_name = 'invoices'

urlpatterns = [
    path('clienti/', views.clients_list, name='clients'),
    path('creare/', views.invoice_create, name='create'),
    path('<int:pk>/', views.invoice_detail, name='detail'),
    path('<int:pk>/finalizeaza/', views.invoice_finalize, name='finalize'),
]
