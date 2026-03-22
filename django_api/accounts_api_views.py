# accounts/api_views.py
# Copiaza acest fisier in AutoHUB-main/accounts/api_views.py

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Car, CarExpiryProfile
from bookings.models import Booking


def get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


def serialize_car(car):
    profile = getattr(car, 'expiry_profile', None)
    docs = []
    if profile:
        today = timezone.localdate()
        for field_name, label, icon, soon_days in CarExpiryProfile.DOCUMENTS:
            expiry_date = getattr(profile, field_name)
            if not expiry_date:
                status = 'missing'; days_left = None
            else:
                days_left = (expiry_date - today).days
                status = 'expired' if days_left < 0 else 'soon' if days_left <= soon_days else 'ok'
            docs.append({'field': field_name, 'label': label, 'date': expiry_date.isoformat() if expiry_date else None, 'status': status, 'days_left': days_left, 'days_overdue': abs(days_left) if days_left is not None and days_left < 0 else 0})
    return {'id': car.pk, 'make': car.make, 'model': car.model, 'year': car.year, 'fuel': car.fuel, 'plate_number': car.plate_number, 'vin': car.vin, 'expiry_profile': docs}


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')
    if not username or not password:
        return Response({'error': 'Username si parola sunt obligatorii.'}, status=400)
    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({'error': 'Date de autentificare incorecte.'}, status=401)
    if not user.is_active:
        return Response({'error': 'Contul nu este activ.'}, status=403)
    tokens = get_tokens(user)
    return Response({'access': tokens['access'], 'refresh': tokens['refresh'], 'user': {'id': user.pk, 'username': user.username, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name}})


@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    username = request.data.get('username', '').strip()
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')
    first_name = request.data.get('first_name', '').strip()
    last_name = request.data.get('last_name', '').strip()
    if not username or not email or not password:
        return Response({'error': 'Toate campurile sunt obligatorii.'}, status=400)
    if User.objects.filter(username__iexact=username).exists():
        return Response({'error': 'Username-ul este deja folosit.'}, status=400)
    if User.objects.filter(email__iexact=email).exists():
        return Response({'error': 'Emailul este deja inregistrat.'}, status=400)
    user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name, last_name=last_name, is_active=True)
    tokens = get_tokens(user)
    return Response({'access': tokens['access'], 'refresh': tokens['refresh'], 'user': {'id': user.pk, 'username': user.username, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name}}, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_profile(request):
    user = request.user
    cars = Car.objects.filter(owner=user).prefetch_related('expiry_profile')
    return Response({'id': user.pk, 'username': user.username, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name, 'cars': [serialize_car(c) for c in cars]})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_cars(request):
    if request.method == 'GET':
        cars = Car.objects.filter(owner=request.user).prefetch_related('expiry_profile')
        return Response({'cars': [serialize_car(c) for c in cars]})
    data = request.data
    if len(data.get('vin', '')) != 17:
        return Response({'error': 'VIN trebuie sa aiba exact 17 caractere.'}, status=400)
    car = Car.objects.create(owner=request.user, make=data['make'].strip(), model=data['model'].strip(), year=data.get('year') or None, fuel=data.get('fuel', '').strip(), plate_number=data['plate_number'].strip().upper(), vin=data['vin'].strip().upper())
    return Response(serialize_car(car), status=201)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_car_detail(request, pk):
    try:
        car = Car.objects.get(pk=pk, owner=request.user)
    except Car.DoesNotExist:
        return Response({'error': 'Masina nu a fost gasita.'}, status=404)
    if request.method == 'GET':
        return Response(serialize_car(car))
    if request.method == 'PUT':
        data = request.data
        car.make = data.get('make', car.make).strip()
        car.model = data.get('model', car.model).strip()
        car.year = data.get('year', car.year) or None
        car.fuel = data.get('fuel', car.fuel).strip()
        car.plate_number = data.get('plate_number', car.plate_number).strip().upper()
        if data.get('vin'):
            if len(data['vin']) != 17:
                return Response({'error': 'VIN invalid.'}, status=400)
            car.vin = data['vin'].strip().upper()
        car.save()
        return Response(serialize_car(car))
    car.delete()
    return Response({'success': True})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_car_expiry(request, pk):
    try:
        car = Car.objects.get(pk=pk, owner=request.user)
    except Car.DoesNotExist:
        return Response({'error': 'Masina nu a fost gasita.'}, status=404)
    profile, _ = CarExpiryProfile.objects.get_or_create(car=car)
    for field in ['itp_expiry', 'rca_expiry', 'rovinieta_expiry', 'casco_expiry', 'trusa_expiry', 'extinctor_expiry']:
        if field in request.data:
            setattr(profile, field, request.data[field] or None)
    profile.save()
    return Response(serialize_car(car))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).select_related('center', 'garage', 'mechanic', 'service_item').order_by('-created_at')
    def serialize(b):
        return {
            'id': b.pk,
            'center': {'id': b.center.pk, 'name': b.center.name, 'slug': b.center.slug, 'city': b.center.get_city_display(), 'phone': b.center.phone} if b.center_id else None,
            'garage': {'id': b.garage.pk, 'name': b.garage.name} if b.garage_id else None,
            'mechanic': {'id': b.mechanic.pk, 'name': b.mechanic.name} if b.mechanic_id else None,
            'service_item': {'id': b.service_item.pk, 'name': b.service_item.name} if b.service_item_id else None,
            'client_name': b.client_name, 'client_phone': b.client_phone, 'client_email': b.client_email,
            'car_brand': b.car_brand, 'car_model': b.car_model, 'car_year': b.car_year, 'car_fuel': b.car_fuel, 'car_plate': b.car_plate, 'car_vin': b.car_vin,
            'problem_description': b.problem_description,
            'booking_date': b.booking_date.isoformat() if b.booking_date else None,
            'booking_time': b.booking_time.strftime('%H:%M') if b.booking_time else None,
            'duration_minutes': b.duration_minutes,
            'estimated_price': str(b.estimated_price) if b.estimated_price else None,
            'status': b.status, 'wants_offer': b.wants_offer,
            'operational_tags': b.operational_tags or [],
            'created_at': b.created_at.isoformat(), 'updated_at': b.updated_at.isoformat(),
        }
    return Response({'bookings': [serialize(b) for b in bookings]})
