"""
API JSON endpoints:
  GET /api/services/         — listare cu filtre standard
  GET /api/services/nearby/  — sortate după distanță față de clientul GPS
"""
import math
from django.http import JsonResponse
from django.db.models import Avg, Count, Min, Max, Q
from .models import ServiceCenter


def _haversine(lat1, lng1, lat2, lng2):
    """Distanța în km între două coordonate GPS (formula Haversine)."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _annotated_qs():
    return ServiceCenter.objects.filter(is_active=True).annotate(
        avg_rating=Avg('review__rating', filter=Q(review__is_approved=True)),
        review_count=Count('review', filter=Q(review__is_approved=True)),
        min_price=Min('serviceitem_set__price_from'),
        max_price=Max('serviceitem_set__price_to'),
    ).select_related('category')


def _serialize(c, distance_km=None):
    mn, mx = c.min_price, getattr(c, 'max_price', None)
    if mn and mx:
        price_range = f"{int(mn)}–{int(mx)} RON"
    elif mn:
        price_range = f"de la {int(mn)} RON"
    else:
        price_range = "La cerere"

    d = {
        'id': c.pk,
        'name': c.name,
        'slug': c.slug,
        'city': c.city,
        'city_display': c.get_city_display(),
        'address': c.address,
        'phone': c.phone,
        'category': c.category.name,
        'category_slug': c.category.slug,
        'category_icon': c.category.icon,
        'rating': round(c.avg_rating, 1) if c.avg_rating else 0,
        'review_count': c.review_count or 0,
        'price_range': price_range,
        'schedule': c.schedule,
        'is_featured': c.is_featured,
        'lat': float(c.latitude) if c.latitude else None,
        'lng': float(c.longitude) if c.longitude else None,
        'url': f'/services/{c.slug}/',
        'booking_url': f'/bookings/programare/{c.slug}/',
    }
    if distance_km is not None:
        d['distance_km'] = round(distance_km, 1)
    return d


def services_api(request):
    """GET /api/services/"""
    qs = _annotated_qs()

    city = request.GET.get('city', '').strip()
    category = request.GET.get('category', '').strip()
    min_rating = request.GET.get('min_rating', '').strip()
    price_min = request.GET.get('price_min', '').strip()
    price_max = request.GET.get('price_max', '').strip()
    q = request.GET.get('q', '').strip()
    limit = min(int(request.GET.get('limit', 50)), 100)

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
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    qs = qs.order_by('-avg_rating')[:limit]
    return JsonResponse({'count': qs.count(), 'results': [_serialize(c) for c in qs]})


def services_nearby(request):
    """
    GET /api/services/nearby/?lat=44.43&lng=26.10&radius=25&category=&limit=10
    Returnează service-urile cel mai apropiate de coordonatele clientului.
    """
    try:
        user_lat = float(request.GET.get('lat', ''))
        user_lng = float(request.GET.get('lng', ''))
    except (ValueError, TypeError):
        return JsonResponse(
            {'error': 'Parametrii lat și lng sunt obligatorii.'},
            status=400
        )

    radius = float(request.GET.get('radius', 50))
    category = request.GET.get('category', '').strip()
    limit = min(int(request.GET.get('limit', 20)), 50)

    qs = _annotated_qs().filter(
        latitude__isnull=False,
        longitude__isnull=False,
    )
    if category:
        qs = qs.filter(category__slug=category)

    # Calculează distanța și filtrează
    with_dist = []
    for c in qs:
        dist = _haversine(user_lat, user_lng, float(c.latitude), float(c.longitude))
        if dist <= radius:
            with_dist.append((dist, c))

    with_dist.sort(key=lambda x: x[0])
    with_dist = with_dist[:limit]

    return JsonResponse({
        'user_location': {'lat': user_lat, 'lng': user_lng},
        'radius_km': radius,
        'count': len(with_dist),
        'results': [_serialize(c, dist) for dist, c in with_dist],
    })
