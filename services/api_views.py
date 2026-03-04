"""
API simplu (fără DRF) — JsonResponse pentru listarea service-urilor.
GET /api/services?city=&category=&min_rating=&price_min=&price_max=

Returnează:
  id, name, city, rating, price_range, category, availability
"""
from django.http import JsonResponse
from django.db.models import Avg, Count, Min, Max, Q
from .models import ServiceCenter


def services_api(request):
    qs = ServiceCenter.objects.filter(is_active=True).annotate(
        avg_rating=Avg('review__rating', filter=Q(review__is_approved=True)),
        review_count=Count('review', filter=Q(review__is_approved=True)),
        # ServiceItem.center folosește related_name='serviceitem_set'
        # deci relația inversă în ORM este serviceitem_set (nu serviceitem).
        min_price=Min('serviceitem_set__price_from'),
        max_price=Max('serviceitem_set__price_to'),
    ).select_related('category')

    # Filtre query params
    city = request.GET.get('city', '').strip()
    category = request.GET.get('category', '').strip()
    min_rating = request.GET.get('min_rating', '').strip()
    price_min = request.GET.get('price_min', '').strip()
    price_max = request.GET.get('price_max', '').strip()
    q = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 50))

    if city:
        qs = qs.filter(city=city)
    if category:
        qs = qs.filter(category__slug=category)
    if min_rating:
        try:
            qs = qs.filter(avg_rating__gte=float(min_rating))
        except ValueError:
            pass
    if price_min:
        try:
            qs = qs.filter(min_price__gte=float(price_min))
        except ValueError:
            pass
    if price_max:
        try:
            qs = qs.filter(min_price__lte=float(price_max))
        except ValueError:
            pass
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q)
        )

    qs = qs.order_by('-avg_rating')[:limit]

    results = []
    for c in qs:
        mn = c.min_price
        mx = c.max_price
        if mn and mx:
            price_range = f"{int(mn)}–{int(mx)} RON"
        elif mn:
            price_range = f"de la {int(mn)} RON"
        else:
            price_range = "La cerere"

        results.append({
            'id': c.pk,
            'name': c.name,
            'slug': c.slug,
            'city': c.city,
            'city_display': c.get_city_display(),
            'address': c.address,
            'phone': c.phone,
            'category': c.category.name,
            'category_slug': c.category.slug,
            'rating': c.avg_rating or 0,
            'review_count': c.review_count or 0,
            'price_range': price_range,
            'availability': c.schedule,
            'is_featured': c.is_featured,
            'url': f'/services/{c.slug}/',
        })

    return JsonResponse({
        'count': len(results),
        'results': results,
    })
