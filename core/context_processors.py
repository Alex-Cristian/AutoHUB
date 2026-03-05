from services.models import ServiceCategory


def global_context(request):
    return {
        'nav_categories': ServiceCategory.objects.order_by('order')[:6],
    }
