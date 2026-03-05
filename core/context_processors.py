from services.models import ServiceCategory


<<<<<<< HEAD
def global_context(request):
    return {
        'nav_categories': ServiceCategory.objects.order_by('order')[:6],
=======
def _service_nav(request):
    """Small helpers for navbar (service dashboard + notification badge)."""
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
            unread = BookingNotification.objects.filter(recipient=request.user, is_read=False).count()
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
    return {
        'nav_categories': ServiceCategory.objects.order_by('order')[:6],
        **_service_nav(request),
>>>>>>> origin/main
    }
