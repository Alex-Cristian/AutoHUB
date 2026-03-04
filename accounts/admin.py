from django.contrib import admin

from .models import Car


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ('owner', 'make', 'model', 'year', 'plate_number', 'fuel', 'created_at')
    list_filter = ('fuel', 'make', 'year')
    search_fields = ('owner__username', 'owner__email', 'make', 'model', 'plate_number', 'vin')
    ordering = ('-created_at',)
