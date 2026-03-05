from django.contrib import admin
from django.utils.html import format_html
<<<<<<< HEAD
from .models import Booking
=======
from .models import Booking, BookingNotification
>>>>>>> origin/main


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'client_name', 'client_phone', 'center',
        'car_info', 'booking_date', 'booking_time',
        'status_badge', 'user_link', 'created_at'
    )
    list_filter = (
        'status', 'booking_date', 'center__city',
        'center__category', 'car_fuel', 'created_at'
    )
    search_fields = (
        'client_name', 'client_phone', 'client_email',
        'car_brand', 'car_model', 'car_plate',
        'center__name', 'problem_description'
    )
    readonly_fields = ('created_at', 'updated_at', 'user')
    date_hierarchy = 'booking_date'
    list_per_page = 25

    fieldsets = (
        ('Date Client', {
            'fields': ('user', 'client_name', 'client_phone', 'client_email')
        }),
        ('Date Mașină', {
            'fields': ('car_brand', 'car_model', 'car_year', 'car_fuel', 'car_plate')
        }),
        ('Programare', {
            'fields': ('center', 'service_item', 'booking_date', 'booking_time', 'problem_description')
        }),
        ('Status & Note', {
            'fields': ('status', 'notes', 'created_at', 'updated_at')
        }),
    )

    actions = ['mark_confirmed', 'mark_done', 'mark_cancelled']

    def car_info(self, obj):
        return f"{obj.car_brand} {obj.car_model} ({obj.car_year})"
    car_info.short_description = 'Mașină'

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'confirmed': '#17a2b8',
            'in_progress': '#007bff',
            'done': '#28a745',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 8px;border-radius:12px;font-size:0.8em;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def user_link(self, obj):
        if obj.user:
            return format_html(
                '<a href="/admin/auth/user/{}/change/">{}</a>',
                obj.user.pk, obj.user.username
            )
        return format_html('<span style="color:#999;">Guest</span>')
    user_link.short_description = 'Cont'

    @admin.action(description='Marchează ca: Confirmată')
    def mark_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed')
        self.message_user(request, f'{updated} programări marcate ca Confirmate.')

    @admin.action(description='Marchează ca: Finalizată')
    def mark_done(self, request, queryset):
        updated = queryset.update(status='done')
        self.message_user(request, f'{updated} programări marcate ca Finalizate.')

    @admin.action(description='Marchează ca: Anulată')
    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} programări marcate ca Anulate.')
<<<<<<< HEAD
=======


@admin.register(BookingNotification)
class BookingNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'kind', 'title', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'recipient__username', 'recipient__email')
    readonly_fields = ('created_at',)
>>>>>>> origin/main
