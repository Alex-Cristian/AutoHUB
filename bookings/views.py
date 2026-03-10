from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Car
from services.models import ServiceCenter, ServiceGarage, ServiceItem
from .ai import estimate_booking_duration, normalize_duration_minutes
from .forms import BookingForm
from .models import Booking, BookingAttachment


def _extract_manual_duration(request):
    raw_value = (
        request.GET.get('duration')
        or request.POST.get('duration')
        or request.GET.get('duration_minutes')
        or request.POST.get('duration_minutes')
        or ''
    )
    raw_value = str(raw_value).strip()
    if not raw_value:
        return None
    digits = ''.join(ch for ch in raw_value if ch.isdigit())
    if not digits:
        return None
    try:
        return normalize_duration_minutes(int(digits))
    except (TypeError, ValueError):
        return None


def _extract_car_data(request):
    car_data = {
        'brand': (request.GET.get('car_brand') or request.POST.get('car_brand') or '').strip(),
        'model': (request.GET.get('car_model') or request.POST.get('car_model') or '').strip(),
        'year': (request.GET.get('car_year') or request.POST.get('car_year') or '').strip(),
        'fuel': (request.GET.get('car_fuel') or request.POST.get('car_fuel') or '').strip(),
        'plate': (request.GET.get('car_plate') or request.POST.get('car_plate') or '').strip(),
        'vin': (request.GET.get('car_vin') or request.POST.get('car_vin') or '').strip(),
    }

    saved_car_id = (request.GET.get('saved_car') or request.POST.get('saved_car') or '').strip()
    if saved_car_id.isdigit():
        car = Car.objects.filter(pk=saved_car_id).first()
        if car:
            car_data = {
                'brand': car.make or car_data['brand'],
                'model': car.model or car_data['model'],
                'year': car.year or car_data['year'],
                'fuel': car.fuel or car_data['fuel'],
                'plate': car.plate_number or car_data['plate'],
                'vin': car.vin or car_data['vin'],
            }
    return car_data


def _get_duration_estimate_from_request(center, request):
    manual_duration = _extract_manual_duration(request)
    service_item = None
    service_id = (request.GET.get('service_item') or request.POST.get('service_item') or '').strip()
    if service_id.isdigit():
        service_item = ServiceItem.objects.filter(center=center, pk=service_id).first()

    if manual_duration is not None:
        return {
            'minutes': manual_duration,
            'source': 'manual',
            'reason': 'Durata a fost aleasă manual.',
            'service_name': getattr(service_item, 'name', ''),
        }

    description = (request.GET.get('problem_description') or request.POST.get('problem_description') or '').strip()
    car_data = _extract_car_data(request)
    estimate = estimate_booking_duration(
        description,
        service_name=getattr(service_item, 'name', ''),
        car_data=car_data,
        center_name=getattr(center, 'name', ''),
    )

    if service_item and getattr(service_item, 'duration_minutes', None):
        estimate['minutes'] = max(normalize_duration_minutes(service_item.duration_minutes), estimate['minutes'])
        estimate['reason'] = (estimate.get('reason') or 'Estimare automată.')[:160]

    estimate['minutes'] = normalize_duration_minutes(estimate.get('minutes'))
    estimate['service_name'] = getattr(service_item, 'name', '')
    estimate['car'] = car_data
    return estimate


def booking_create(request, slug):
    center = get_object_or_404(ServiceCenter.objects.prefetch_related('garages'), slug=slug, is_active=True)

    if request.method == 'POST':
        form = BookingForm(center=center, user=request.user, data=request.POST, files=request.FILES)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.center = center
            booking.duration_minutes = _get_duration_estimate_from_request(center, request).get('minutes')
            if request.user.is_authenticated:
                booking.user = request.user
            booking.full_clean()
            booking.save()

            for uploaded in request.FILES.getlist('attachments'):
                content_type = getattr(uploaded, 'content_type', '') or ''
                media_kind = 'video' if content_type.startswith('video/') else 'image'
                BookingAttachment.objects.create(booking=booking, file=uploaded, media_kind=media_kind)

            garage_label = f' în {booking.garage.name}' if booking.garage_id else ''
            messages.success(
                request,
                f'✅ Programare trimisă{garage_label}! Vă așteptăm pe {booking.booking_date.strftime("%d %B %Y")} la ora {booking.booking_time.strftime("%H:%M")}.',
            )
            return redirect('bookings:success', pk=booking.pk)
    else:
        form = BookingForm(center=center, user=request.user)

    cars = []
    if request.user.is_authenticated:
        cars = Car.objects.filter(owner=request.user).order_by('make', 'model', 'plate_number')

    context = {
        'center': center,
        'form': form,
        'cars': cars,
    }
    return render(request, 'bookings/booking_create.html', context)


def booking_success(request, pk):
    booking = get_object_or_404(Booking.objects.select_related('center', 'garage'), pk=pk)
    if booking.user and request.user != booking.user and not request.user.is_staff:
        return redirect('core:home')
    return render(request, 'bookings/booking_success.html', {'booking': booking})


@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).select_related(
        'center', 'center__category', 'service_item', 'garage'
    ).prefetch_related('attachments').order_by('-created_at')
    return render(request, 'bookings/my_bookings.html', {'bookings': bookings})


@login_required
@require_POST
def attachment_delete(request, pk):
    attachment = get_object_or_404(BookingAttachment.objects.select_related('booking', 'booking__center'), pk=pk)
    booking = attachment.booking
    if not (
        request.user.is_staff
        or booking.user_id == request.user.id
        or booking.center.owner_id == request.user.id
    ):
        return redirect('core:home')

    booking_pk = booking.pk
    file_storage = attachment.file
    attachment.delete()
    if file_storage:
        file_storage.delete(save=False)
    messages.info(request, 'Fișierul a fost șters.')

    if booking.center.owner_id == request.user.id or request.user.is_staff:
        return redirect('services:booking_detail', pk=booking_pk)
    return redirect('bookings:my_bookings')


@require_GET
def booking_duration_estimate(request, slug):
    center = get_object_or_404(ServiceCenter, slug=slug, is_active=True)
    estimate = _get_duration_estimate_from_request(center, request)
    return JsonResponse(estimate)


@require_GET
def garage_slots(request, slug):
    center = get_object_or_404(ServiceCenter, slug=slug, is_active=True)
    garage_id = request.GET.get('garage')
    date_str = request.GET.get('date')
    if not garage_id or not date_str:
        return JsonResponse({'slots': [], 'error': 'Lipsesc garajul sau data.'}, status=400)

    garage = get_object_or_404(ServiceGarage, pk=garage_id, center=center)
    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'slots': [], 'error': 'Data nu este validă.'}, status=400)

    estimate = _get_duration_estimate_from_request(center, request)
    duration_minutes = normalize_duration_minutes(estimate.get('minutes'))
    slots = garage.available_slots_for_date(booking_date, duration_minutes=duration_minutes)
    return JsonResponse({
        'garage': garage.name,
        'open_time': garage.open_time.strftime('%H:%M'),
        'close_time': garage.close_time.strftime('%H:%M'),
        'slot_minutes': 30,
        'duration_minutes': duration_minutes,
        'estimate_source': estimate.get('source', 'fallback'),
        'estimate_reason': estimate.get('reason', ''),
        'service_name': estimate.get('service_name', ''),
        'slots': slots,
    })
