from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Car
from services.models import ServiceCenter, ServiceGarage, ServiceItem, ServiceCategory
from .ai import estimate_booking_duration, normalize_duration_minutes
from .forms import BookingForm
from .models import Booking, BookingAttachment, BookingNotification
from .activity import log_booking_activity
from core.services.email_service import send_quote_accepted_to_service_email
from core.upload_validators import validate_booking_media_file


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
    center = get_object_or_404(
        ServiceCenter.objects.prefetch_related('garages', 'garages__category', 'categories'),
        slug=slug, is_active=True
    )

    if request.method == 'POST':
        form = BookingForm(center=center, user=request.user, data=request.POST, files=request.FILES)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.center = center
            booking.duration_minutes = _get_duration_estimate_from_request(center, request).get('minutes')
            booking.wants_offer = request.POST.get('wants_offer') == '1'
            if request.user.is_authenticated:
                booking.user = request.user
            booking.full_clean()
            booking.save()
            log_booking_activity(booking, 'schedule_changed', 'Programarea a fost creata de client.', actor=request.user if request.user.is_authenticated else None)

            for uploaded in request.FILES.getlist('attachments'):
                validate_booking_media_file(uploaded)
                content_type = getattr(uploaded, 'content_type', '') or ''
                media_kind = 'video' if content_type.startswith('video/') else 'image'
                BookingAttachment.objects.create(booking=booking, file=uploaded, media_kind=media_kind)
                log_booking_activity(
                    booking,
                    'attachment_added',
                    f'Clientul a adaugat un fisier: {uploaded.name}.',
                    actor=request.user if request.user.is_authenticated else None,
                    metadata={'filename': uploaded.name, 'media_kind': media_kind},
                )

            if request.user.is_authenticated and request.POST.get('save_car') == '1':
                saved_car_id = request.POST.get('saved_car', '').strip()
                if not saved_car_id:
                    fuel_val = booking.car_fuel if booking.car_fuel else ''
                    Car.objects.get_or_create(
                        owner=request.user,
                        plate_number=booking.car_plate,
                        defaults={
                            'make': booking.car_brand,
                            'model': booking.car_model,
                            'year': booking.car_year,
                            'fuel': fuel_val,
                            'vin': booking.car_vin,
                        }
                    )
                    messages.info(request, f'🚗 Mașina {booking.car_brand} {booking.car_model} a fost salvată în contul tău.')

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

    center_cat_ids = set(center.categories.values_list('id', flat=True))
    if center.category_id:
        center_cat_ids.add(center.category_id)
    categories = ServiceCategory.objects.filter(id__in=center_cat_ids).order_by('order', 'name')

    context = {
        'center': center,
        'form': form,
        'cars': cars,
        'categories': categories,
    }
    return render(request, 'bookings/booking_create.html', context)


def booking_success(request, pk):
    booking = get_object_or_404(Booking.objects.select_related('center', 'garage'), pk=pk)
    if booking.user and request.user != booking.user and not request.user.is_staff:
        return redirect('core:home')
    return render(request, 'bookings/booking_success.html', {'booking': booking})


@login_required
def my_bookings(request):
    from services.models import MechanicWorkLog

    bookings = Booking.objects.filter(user=request.user).select_related(
        'center', 'center__category', 'service_item', 'garage', 'mechanic'
    ).prefetch_related(
        'attachments',
        'job_card__recommendations',
        'job_card__part_usages__part',
        'invoices',
    ).order_by('-created_at')

    booking_list = list(bookings)
    for b in booking_list:
        b.mechanic_work_log = None
        b.job_card_obj = None
        if b.mechanic_id:
            try:
                b.mechanic_work_log = MechanicWorkLog.objects.filter(
                    booking=b
                ).prefetch_related('photos').first()
            except Exception:
                pass
        try:
            b.job_card_obj = b.job_card
        except Exception:
            b.job_card_obj = None

    return render(request, 'bookings/my_bookings.html', {'bookings': booking_list})


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


@require_GET
def garaje_disponibile(request, slug):
    center = get_object_or_404(
        ServiceCenter.objects.prefetch_related('garages__category', 'categories'),
        slug=slug, is_active=True
    )

    category_slug = request.GET.get('category', '').strip()
    date_str = request.GET.get('date', '').strip()

    if not date_str:
        return JsonResponse({'garages': [], 'error': 'Data este obligatorie.'}, status=400)

    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'garages': [], 'error': 'Format dată invalid.'}, status=400)

    estimate = _get_duration_estimate_from_request(center, request)
    duration_minutes = normalize_duration_minutes(estimate.get('minutes'))

    garages_qs = center.garages.select_related('category')
    if category_slug:
        garages_qs = garages_qs.filter(category__slug=category_slug)

    result = []
    for garage in garages_qs:
        slots = garage.available_slots_for_date(booking_date, duration_minutes=duration_minutes)
        result.append({
            'id': garage.pk,
            'name': garage.name,
            'category': garage.category.name,
            'category_slug': garage.category.slug,
            'open_time': garage.open_time.strftime('%H:%M'),
            'close_time': garage.close_time.strftime('%H:%M'),
            'slots': slots,
            'slots_count': len(slots),
        })

    return JsonResponse({
        'center': center.name,
        'date': date_str,
        'duration_minutes': duration_minutes,
        'estimate_source': estimate.get('source', 'fallback'),
        'estimate_reason': estimate.get('reason', ''),
        'garages': result,
    })

@login_required
@require_POST
def booking_accept_quote(request, pk):
    booking = get_object_or_404(Booking.objects.select_related('garage', 'center'), pk=pk, user=request.user)
    if booking.status != Booking.STATUS_QUOTED:
        messages.info(request, 'Această ofertă nu mai așteaptă răspunsul tău.')
        return redirect('bookings:my_bookings')

    if booking.garage_id and not booking.garage.is_time_available(
        booking.booking_date,
        booking.booking_time,
        duration_minutes=booking.effective_duration_minutes(),
        exclude_booking_id=booking.pk,
        booking_status=Booking.STATUS_CONFIRMED,
    ):
        messages.error(request, 'Intervalul nu mai este disponibil. Service-ul trebuie să îți trimită o ofertă nouă.')
        booking.status = Booking.STATUS_PENDING
        booking.save(update_fields=['status', 'updated_at'])
        return redirect('bookings:my_bookings')

    booking.status = Booking.STATUS_CONFIRMED
    booking.save(update_fields=['status', 'updated_at'])
    log_booking_activity(
        booking,
        'status_changed',
        'Clientul a acceptat oferta service-ului.',
        actor=request.user,
        metadata={'old': Booking.STATUS_QUOTED, 'new': Booking.STATUS_CONFIRMED},
    )
    if booking.center.owner_id:
        BookingNotification.objects.create(
            recipient=booking.center.owner,
            booking=booking,
            kind=BookingNotification.KIND_STATUS_UPDATE,
            title=f'Clientul a confirmat programarea #{booking.pk} ✅',
            message=(
                f'{booking.client_name} a acceptat oferta pentru {booking.booking_date} la '
                f"{booking.booking_time.strftime('%H:%M')} ({booking.get_duration_display()})."
            ),
        )
    send_quote_accepted_to_service_email(booking)
    messages.success(request, 'Ai confirmat programarea. Service-ul a rezervat intervalul pentru tine.')
    return redirect('bookings:my_bookings')


@login_required
@require_POST
def booking_reject_quote(request, pk):
    booking = get_object_or_404(Booking.objects.select_related('center'), pk=pk, user=request.user)
    if booking.status != Booking.STATUS_QUOTED:
        messages.info(request, 'Această ofertă nu mai așteaptă răspunsul tău.')
        return redirect('bookings:my_bookings')

    booking.status = Booking.STATUS_CANCELLED
    booking.save(update_fields=['status', 'updated_at'])
    log_booking_activity(
        booking,
        'status_changed',
        'Clientul a refuzat oferta service-ului.',
        actor=request.user,
        metadata={'old': Booking.STATUS_QUOTED, 'new': Booking.STATUS_CANCELLED},
    )
    if booking.center.owner_id:
        BookingNotification.objects.create(
            recipient=booking.center.owner,
            booking=booking,
            kind=BookingNotification.KIND_STATUS_UPDATE,
            title=f'Clientul a refuzat oferta pentru programarea #{booking.pk}',
            message=f'{booking.client_name} a refuzat oferta trimisă de service.',
        )
    messages.info(request, 'Ai refuzat oferta pentru această programare.')
    return redirect('bookings:my_bookings')
