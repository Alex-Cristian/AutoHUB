from django.contrib import admin
from django.utils.html import format_html
from .models import ServiceCategory, ServiceCenter, ServiceItem, Review, Favorite


class ServiceItemInline(admin.TabularInline):
    model = ServiceItem
    extra = 2
    fields = ('name', 'price_from', 'price_to', 'duration_minutes', 'is_popular')
    show_change_link = True


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('icon', 'name', 'slug', 'color', 'order', 'center_count_display')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

    def center_count_display(self, obj):
        count = obj.servicecenter_set.filter(is_active=True).count()
        return format_html('<strong>{}</strong> service-uri', count)
    center_count_display.short_description = 'Service-uri active'


@admin.register(ServiceCenter)
class ServiceCenterAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'city_display', 'phone',
        'avg_rating_display', 'review_count_display',
        'verification_status', 'is_active', 'is_featured', 'created_at'
    )
    list_filter = ('category', 'city', 'verification_status', 'is_active', 'is_featured', 'created_at')
    search_fields = ('name', 'address', 'phone', 'email', 'description')
    list_editable = ('is_active', 'is_featured')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'avg_rating_display', 'review_count_display', 'verified_at')
    inlines = [ServiceItemInline]
    fieldsets = (
        ('Informații Principale', {
            'fields': ('name', 'slug', 'category', 'description', 'owner')
        }),
        ('Contact & Locație', {
            'fields': ('address', 'city', 'phone', 'email', 'website', 'schedule', 'latitude', 'longitude')
        }),
        ('Date legale (opțional)', {
            'fields': ('legal_name', 'headquarters', 'fiscal_code', 'trade_register_no', 'legal_document'),
            'classes': ('collapse',)
        }),
        ('Verificare (intern)', {
            'fields': ('verification_status', 'verification_note', 'verified_at'),
        }),
        ('Setări', {
            'fields': ('is_active', 'is_featured', 'created_at')
        }),
        ('Statistici', {
            'fields': ('avg_rating_display', 'review_count_display'),
            'classes': ('collapse',)
        }),
    )

    def city_display(self, obj):
        return obj.get_city_display()
    city_display.short_description = 'Oraș'
    city_display.admin_order_field = 'city'

    def avg_rating_display(self, obj):
        rating = obj.avg_rating()
        if rating:
            stars = '★' * int(round(rating)) + '☆' * (5 - int(round(rating)))
            return format_html('<span style="color:#f4a261;">{}</span> <strong>{}</strong>', stars, rating)
        return '—'
    avg_rating_display.short_description = 'Rating mediu'

    def review_count_display(self, obj):
        return obj.review_count()
    review_count_display.short_description = 'Nr. recenzii'


@admin.register(ServiceItem)
class ServiceItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'center', 'price_display_col', 'duration_minutes', 'is_popular')
    list_filter = ('is_popular', 'center__category', 'center__city')
    search_fields = ('name', 'center__name', 'description')
    list_editable = ('is_popular',)

    def price_display_col(self, obj):
        return obj.price_display()
    price_display_col.short_description = 'Preț orientativ'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'center', 'rating_stars', 'title',
        'is_approved', 'created_at'
    )
    list_filter = ('rating', 'is_approved', 'created_at', 'center__city', 'center__category')
    search_fields = ('user__username', 'user__email', 'center__name', 'title', 'body')
    list_editable = ('is_approved',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    def rating_stars(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span style="color:#f4a261; font-size:1.1em;">{}</span>', stars)
    rating_stars.short_description = 'Rating'
    rating_stars.admin_order_field = 'rating'


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'center', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'center__name')
