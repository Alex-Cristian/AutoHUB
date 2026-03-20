from django.contrib import admin

from .models import Car, CarExpiryProfile, EmailVerificationToken, CarExpiryReminderLog


class CarExpiryProfileInline(admin.StackedInline):
    model = CarExpiryProfile
    extra = 0
    can_delete = False


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ('owner', 'make', 'model', 'year', 'plate_number', 'fuel', 'created_at')
    list_filter = ('fuel', 'make', 'year')
    search_fields = ('owner__username', 'owner__email', 'make', 'model', 'plate_number', 'vin')
    ordering = ('-created_at',)
    inlines = [CarExpiryProfileInline]


@admin.register(CarExpiryProfile)
class CarExpiryProfileAdmin(admin.ModelAdmin):
    list_display = ('car', 'itp_expiry', 'rca_expiry', 'rovinieta_expiry', 'trusa_expiry', 'extinctor_expiry', 'updated_at')
    search_fields = ('car__plate_number', 'car__make', 'car__model', 'car__owner__username', 'car__owner__email')


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'verified_at')
    search_fields = ('user__username', 'user__email', 'token')


@admin.register(CarExpiryReminderLog)
class CarExpiryReminderLogAdmin(admin.ModelAdmin):
    list_display = ('car', 'document_type', 'expiry_date', 'sent_at')
    search_fields = ('car__plate_number', 'car__owner__email', 'document_type')
