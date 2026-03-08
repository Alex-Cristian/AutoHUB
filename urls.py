from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls', namespace='core')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('services/', include('services.urls', namespace='services')),
    path('bookings/', include('bookings.urls', namespace='bookings')),
    path('facturi/', include('invoices.urls', namespace='invoices')),
    path('api/', include('services.api_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
