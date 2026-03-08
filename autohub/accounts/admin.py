from django.contrib import admin

from .models import Car, CarExpiryCalendar


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ('owner', 'make', 'model', 'year', 'plate_number', 'fuel', 'created_at')
    list_filter = ('fuel', 'make', 'year')
    search_fields = ('owner__username', 'owner__email', 'make', 'model', 'plate_number', 'vin')
    ordering = ('-created_at',)


@admin.register(CarExpiryCalendar)
class CarExpiryCalendarAdmin(admin.ModelAdmin):
    list_display = ('car', 'itp_expiry', 'rca_expiry', 'rovinieta_expiry', 'trusa_expiry', 'extinctor_expiry', 'updated_at')
    search_fields = ('car__plate_number', 'car__make', 'car__model', 'car__owner__username')
    ordering = ('-updated_at',)
