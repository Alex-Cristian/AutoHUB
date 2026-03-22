# services/api_views_extended.py
# Copiaza in AutoHUB-main/services/api_views_extended.py

from django.db.models import Avg, Count, Min, Max, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import ServiceCenter, ServiceCategory, ServiceItem, ServiceGarage, Review, Favorite


def serialize_category(cat):
    return {'id': cat.pk, 'name': cat.name, 'slug': cat.slug, 'icon': cat.icon, 'color': cat.color, 'description': cat.description}


def serialize_service_full(c, user=None):
    reviews = c.review_set.filter(is_approved=True).order_by('-created_at')[:10]
    items = c.serviceitem_set.all().order_by('name')
    garages = c.garages.all()
    avg = c.review_set.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg']
    count = c.review_set.filter(is_approved=True).count()
    min_p = c.serviceitem_set.aggregate(m=Min('price_from'))['m']
    max_p = c.serviceitem_set.aggregate(m=Max('price_to'))['m']
    if min_p and max_p: price_range = f"{int(min_p)}-{int(max_p)} RON"
    elif min_p: price_range = f"de la {int(min_p)} RON"
    else: price_range = "La cerere"
    is_fav = Favorite.objects.filter(user=user, center=c).exists() if user and user.is_authenticated else False
    return {
        'id': c.pk, 'name': c.name, 'slug': c.slug, 'description': c.description,
        'address': c.address, 'city': c.city, 'city_display': c.get_city_display(),
        'phone': c.phone, 'email': c.email, 'website': c.website, 'schedule': c.schedule,
        'lat': float(c.latitude) if c.latitude else None, 'lng': float(c.longitude) if c.longitude else None,
        'category': c.category.name if c.category_id else '', 'category_slug': c.category.slug if c.category_id else '',
        'categories': [serialize_category(cat) for cat in c.display_categories()],
        'rating': round(avg, 1) if avg else 0, 'review_count': count,
        'price_range': price_range, 'is_featured': c.is_featured, 'is_favorited': is_fav,
        'images': [c.card_image.url] if c.card_image else [],
        'service_items': [{'id': item.pk, 'name': item.name, 'description': getattr(item, 'description', ''), 'price_from': str(item.price_from) if item.price_from else None, 'price_to': str(item.price_to) if item.price_to else None, 'duration_minutes': getattr(item, 'duration_minutes', None), 'category': item.category.name if hasattr(item, 'category') and item.category_id else ''} for item in items],
        'garages': [{'id': g.pk, 'name': g.name, 'category': g.category.name if g.category_id else '', 'open_time': g.open_time.strftime('%H:%M'), 'close_time': g.close_time.strftime('%H:%M'), 'slot_minutes': g.slot_minutes} for g in garages],
        'reviews': [{'id': r.pk, 'author': r.user.get_full_name() or r.user.username if r.user_id else 'Anonim', 'rating': r.rating, 'comment': getattr(r, 'comment', ''), 'created_at': r.created_at.isoformat() if hasattr(r, 'created_at') else ''} for r in reviews],
        'verification_status': c.verification_status,
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def api_categories(request):
    cats = ServiceCategory.objects.all().order_by('order', 'name')
    return Response({'categories': [serialize_category(c) for c in cats]})


@api_view(['GET'])
@permission_classes([AllowAny])
def api_service_detail(request, slug):
    try:
        c = ServiceCenter.objects.filter(is_active=True).prefetch_related('review_set', 'serviceitem_set', 'garages', 'categories').get(slug=slug)
    except ServiceCenter.DoesNotExist:
        return Response({'error': 'Service-ul nu a fost gasit.'}, status=404)
    return Response(serialize_service_full(c, request.user))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_favorites(request):
    favs = Favorite.objects.filter(user=request.user).select_related('center', 'center__category')
    result = []
    for fav in favs:
        c = fav.center
        avg = c.review_set.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg']
        min_p = c.serviceitem_set.aggregate(m=Min('price_from'))['m']
        result.append({'id': c.pk, 'name': c.name, 'slug': c.slug, 'city': c.city, 'city_display': c.get_city_display(), 'address': c.address, 'category': c.category.name if c.category_id else '', 'category_slug': c.category.slug if c.category_id else '', 'category_icon': c.category.icon if c.category_id else '', 'rating': round(avg, 1) if avg else 0, 'review_count': c.review_set.filter(is_approved=True).count(), 'price_range': f"de la {int(min_p)} RON" if min_p else "La cerere", 'is_featured': c.is_featured, 'is_favorited': True, 'schedule': c.schedule, 'lat': float(c.latitude) if c.latitude else None, 'lng': float(c.longitude) if c.longitude else None})
    return Response({'favorites': result})


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_toggle_favorite(request, slug):
    try:
        center = ServiceCenter.objects.get(slug=slug, is_active=True)
    except ServiceCenter.DoesNotExist:
        return Response({'error': 'Service-ul nu a fost gasit.'}, status=404)
    fav, created = Favorite.objects.get_or_create(user=request.user, center=center)
    if not created:
        fav.delete()
        return Response({'is_favorited': False})
    return Response({'is_favorited': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_add_review(request, slug):
    try:
        center = ServiceCenter.objects.get(slug=slug, is_active=True)
    except ServiceCenter.DoesNotExist:
        return Response({'error': 'Service-ul nu a fost gasit.'}, status=404)
    rating = request.data.get('rating')
    if not rating or int(rating) not in [1, 2, 3, 4, 5]:
        return Response({'error': 'Rating invalid.'}, status=400)
    Review.objects.create(user=request.user, center=center, rating=int(rating), is_approved=False)
    return Response({'success': True, 'message': 'Recenzia asteapta aprobare.'}, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_owner_dashboard(request):
    from bookings.models import Booking
    from django.utils import timezone
    center = ServiceCenter.objects.filter(owner=request.user, is_active=True).first()
    if not center:
        return Response({'error': 'Nu ai un service asociat.'}, status=403)
    today = timezone.localdate()
    return Response({
        'center': {'id': center.pk, 'name': center.name, 'slug': center.slug, 'verification_status': center.verification_status},
        'stats': {
            'bookings_today': Booking.objects.filter(center=center, booking_date=today).count(),
            'bookings_active': Booking.objects.filter(center=center, status__in=['pending', 'confirmed', 'in_progress', 'quoted']).count(),
            'bookings_pending': Booking.objects.filter(center=center, status='pending').count(),
            'avg_rating': round(center.review_set.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg'] or 0, 1),
            'total_reviews': center.review_set.filter(is_approved=True).count(),
            'total_garages': center.garages.count(),
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_owner_bookings(request):
    from bookings.models import Booking
    center = ServiceCenter.objects.filter(owner=request.user, is_active=True).first()
    if not center:
        return Response({'error': 'Nu ai un service asociat.'}, status=403)
    qs = Booking.objects.filter(center=center).select_related('user', 'garage', 'mechanic', 'service_item').order_by('-created_at')
    if request.GET.get('status'): qs = qs.filter(status=request.GET['status'])
    if request.GET.get('date'): qs = qs.filter(booking_date=request.GET['date'])
    def s(b):
        return {'id': b.pk, 'client_name': b.client_name, 'client_phone': b.client_phone, 'client_email': b.client_email, 'car_brand': b.car_brand, 'car_model': b.car_model, 'car_plate': b.car_plate, 'car_vin': b.car_vin, 'car_year': b.car_year, 'car_fuel': b.car_fuel, 'problem_description': b.problem_description, 'booking_date': b.booking_date.isoformat() if b.booking_date else None, 'booking_time': b.booking_time.strftime('%H:%M') if b.booking_time else None, 'duration_minutes': b.duration_minutes, 'estimated_price': str(b.estimated_price) if b.estimated_price else None, 'status': b.status, 'wants_offer': b.wants_offer, 'operational_tags': b.operational_tags or [], 'garage': {'id': b.garage.pk, 'name': b.garage.name} if b.garage_id else None, 'mechanic': {'id': b.mechanic.pk, 'name': b.mechanic.name} if b.mechanic_id else None, 'notes': b.notes, 'created_at': b.created_at.isoformat()}
    return Response({'bookings': [s(b) for b in qs]})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_owner_booking_update(request, pk):
    from bookings.models import Booking
    center = ServiceCenter.objects.filter(owner=request.user, is_active=True).first()
    if not center:
        return Response({'error': 'Nu ai un service asociat.'}, status=403)
    try:
        booking = Booking.objects.get(pk=pk, center=center)
    except Booking.DoesNotExist:
        return Response({'error': 'Programarea nu a fost gasita.'}, status=404)
    for field in ['status', 'notes', 'estimated_price', 'duration_minutes', 'garage_id', 'mechanic_id', 'operational_tags']:
        if field in request.data:
            setattr(booking, field, request.data[field])
    booking.save()
    return Response({'success': True, 'status': booking.status})
