from django.core.cache import cache
from services.models import ServiceCategory


def _service_nav(request):
    """
    Navbar context pentru service owner + badge notificări.
    Optimizare: query-uri reduse, fără overhead inutil.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'has_service_center': False,
            'service_unread_notifications': 0,
        }

    try:
        from services.models import ServiceCenter
        from bookings.models import BookingNotification

        has_center = ServiceCenter.objects.filter(owner=request.user).exists()
        unread = 0
        if has_center:
            unread = BookingNotification.objects.filter(
                recipient=request.user, is_read=False
            ).count()
        return {
            'has_service_center': has_center,
            'service_unread_notifications': unread,
        }
    except Exception:
        return {
            'has_service_center': False,
            'service_unread_notifications': 0,
        }


def global_context(request):
    # Cache categorii navbar 5 minute — nu se schimbă des, nu merită query la fiecare request
    nav_categories = cache.get('nav_categories')
    if nav_categories is None:
        nav_categories = list(ServiceCategory.objects.order_by('order')[:6])
        cache.set('nav_categories', nav_categories, 300)

    return {
        'nav_categories': nav_categories,
        **_service_nav(request),
    }