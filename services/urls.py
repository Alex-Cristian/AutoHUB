from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    path('', views.service_list, name='list'),
    path('categorii/', views.category_list, name='categories'),
    path('<slug:slug>/', views.service_detail, name='detail'),
    path('<slug:slug>/favorit/', views.toggle_favorite, name='toggle_favorite'),
]
