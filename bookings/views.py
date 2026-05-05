from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Car
from services.business import transition_booking_status
from services.models import ServiceCenter, ServiceGarage, ServiceItem, ServiceCategory
from .ai import estimate_booking_duration, heuristic_duration_estimate, normalize_duration_minutes
from .forms import BookingForm, WEEKDAY_LABELS
from .models import Booking, BookingAttachment, BookingNotification
from .activity import log_booking_activity
from .availability import booking_slot_is_available
from .files import (
    attachment_content_type,
    attachment_display_name,
    build_attachment_summary,
    prepare_uploaded_file,
)
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


def _safe_duration_estimate(center, request):
    try:
        return _get_duration_estimate_from_request(center, request)
    except Exception:
        service_item = None
        service_id = (request.GET.get('service_item') or request.POST.get('service_item') or '').strip()
        if service_id.isdigit():
            service_item = ServiceItem.objects.filter(center=center, pk=service_id).first()
        description = (request.GET.get('problem_description') or request.POST.get('problem_description') or '').strip()
        car_data = _extract_car_data(request)
        estimate = heuristic_duration_estimate(
            description,
            service_name=getattr(service_item, 'name', ''),
            car_data=car_data,
            center_name=getattr(center, 'name', ''),
        )
        estimate['minutes'] = normalize_duration_minutes(estimate.get('minutes'))
        estimate['service_name'] = getattr(service_item, 'name', '')
        estimate['car'] = car_data
        estimate['source'] = estimate.get('source', 'catalog')
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
            estimate = _get_duration_estimate_from_request(center, request)
            booking.duration_minutes = estimate.get('minutes')
            booking.estimated_operation_slug = estimate.get('operation_slug', '')
            booking.estimated_operation_label = estimate.get('operation_label', '')
            booking.duration_estimate_source = estimate.get('source', '')
            booking.duration_estimate_confidence = estimate.get('confidence')
            booking.wants_offer = request.POST.get('wants_offer') == '1'
            if request.user.is_authenticated:
                booking.user = request.user
            booking.full_clean()
            booking.save()
            log_booking_activity(booking, 'schedule_changed', 'Cererea a fost trimisa de client.', actor=request.user if request.user.is_authenticated else None)

            added_count = 0
            image_count = 0
            video_count = 0
            for uploaded in request.FILES.getlist('attachments'):
                uploaded = prepare_uploaded_file(uploaded)
                validate_booking_media_file(uploaded)
                content_type = getattr(uploaded, 'content_type', '') or ''
                media_kind = 'video' if content_type.startswith('video/') else 'image'
                BookingAttachment.objects.create(booking=booking, file=uploaded, media_kind=media_kind)
                added_count += 1
                if media_kind == 'image':
                    image_count += 1
                else:
                    video_count += 1

            if added_count:
                log_booking_activity(
                    booking,
                    'attachment_added',
                    build_attachment_summary(
                        actor_label='Clientul',
                        count=added_count,
                        image_count=image_count,
                        video_count=video_count,
                    ),
                    actor=request.user if request.user.is_authenticated else None,
                    metadata={'count': added_count, 'image_count': image_count, 'video_count': video_count},
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

            garage_label = f' pentru postul preferat {booking.garage.name}' if booking.garage_id else ''
            messages.success(
                request,
                f'Cererea a fost trimisa{garage_label}. Service-ul va confirma, va propune alt interval sau va respinge solicitarea dupa analiza.',
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
        'allowed_weekdays': sorted(getattr(form, 'allowed_weekdays', {0, 1, 2, 3, 4})),
        'allowed_weekday_labels': [WEEKDAY_LABELS[idx] for idx in sorted(getattr(form, 'allowed_weekdays', {0, 1, 2, 3, 4}))],
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
    work_logs = {
        work_log.booking_id: work_log
        for work_log in MechanicWorkLog.objects.filter(booking__in=booking_list).prefetch_related('photos')
    }
    for b in booking_list:
        b.mechanic_work_log = work_logs.get(b.pk)
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


@login_required
def attachment_file(request, pk):
    attachment = get_object_or_404(BookingAttachment.objects.select_related('booking', 'booking__center'), pk=pk)
    booking = attachment.booking
    if not (
        request.user.is_staff
        or booking.user_id == request.user.id
        or booking.center.owner_id == request.user.id
    ):
        return redirect('core:home')

    try:
        attachment.file.open('rb')
    except FileNotFoundError as exc:
        raise Http404('Fisierul nu mai exista in stocare.') from exc

    response = FileResponse(attachment.file, content_type=attachment_content_type(attachment))
    response['Content-Disposition'] = f'inline; filename="{attachment_display_name(attachment)}"'
    return response


@require_GET
def booking_duration_estimate(request, slug):
    center = get_object_or_404(ServiceCenter, slug=slug, is_active=True)
    estimate = _safe_duration_estimate(center, request)
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

    estimate = _safe_duration_estimate(center, request)
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

    estimate = _safe_duration_estimate(center, request)
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

    if booking.needs_client_reschedule:
        messages.error(request, 'Alege un nou interval disponibil inainte sa accepti oferta.')
        return redirect('bookings:my_bookings')

    if booking.garage_id and not booking.garage.is_time_available(
        booking.booking_date,
        booking.booking_time,
        duration_minutes=booking.effective_duration_minutes(),
        exclude_booking_id=booking.pk,
        booking_status=Booking.STATUS_CONFIRMED,
    ):
        messages.error(request, 'Intervalul nu mai este disponibil. Service-ul trebuie să îți trimită o ofertă nouă.')
        transition_booking_status(booking, Booking.STATUS_PENDING, actor=request.user)
        return redirect('bookings:my_bookings')

    transition_booking_status(booking, Booking.STATUS_CONFIRMED, actor=request.user)
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
            title=f'Clientul a confirmat propunerea pentru cererea #{booking.pk} ✅',
            message=(
                f'{booking.client_name} a acceptat propunerea pentru {booking.booking_date} la '
                f"{booking.booking_time.strftime('%H:%M')} ({booking.get_duration_display()})."
            ),
        )
    send_quote_accepted_to_service_email(booking)
    messages.success(request, 'Ai confirmat propunerea service-ului. Programarea poate fi preluata acum si in sistemul intern al service-ului.')
    return redirect('bookings:my_bookings')


@login_required
@require_POST
def booking_reschedule_quote(request, pk):
    booking = get_object_or_404(Booking.objects.select_related('garage', 'mechanic', 'center'), pk=pk, user=request.user)
    if booking.status != Booking.STATUS_QUOTED or not booking.needs_client_reschedule:
        messages.info(request, 'Aceasta oferta nu necesita alegerea unui nou interval.')
        return redirect('bookings:my_bookings')

    date_str = (request.POST.get('booking_date') or '').strip()
    time_str = (request.POST.get('booking_time') or '').strip()
    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        booking_time = datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
        messages.error(request, 'Alege o data si o ora valida pentru reprogramare.')
        return redirect('bookings:my_bookings')

    duration_minutes = booking.effective_duration_minutes()
    if not booking_slot_is_available(booking, booking_date, booking_time, duration_minutes):
        messages.error(request, 'Intervalul ales nu mai este disponibil. Te rugam sa alegi alta zi sau ora.')
        return redirect('bookings:my_bookings')

    old_date = booking.booking_date
    old_time = booking.booking_time
    booking.booking_date = booking_date
    booking.booking_time = booking_time
    booking.needs_client_reschedule = False
    try:
        booking.full_clean()
        booking.save(update_fields=['booking_date', 'booking_time', 'needs_client_reschedule', 'updated_at'])
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('bookings:my_bookings')

    log_booking_activity(
        booking,
        'schedule_changed',
        'Clientul a ales un nou interval pentru oferta service-ului.',
        actor=request.user,
        metadata={
            'old_date': old_date.isoformat() if old_date else '',
            'old_time': old_time.strftime('%H:%M') if old_time else '',
            'new_date': booking.booking_date.isoformat(),
            'new_time': booking.booking_time.strftime('%H:%M'),
            'duration_minutes': duration_minutes,
        },
    )
    messages.success(request, 'Noul interval a fost salvat. Acum poti accepta sau refuza oferta.')
    return redirect('bookings:my_bookings')


@login_required
@require_POST
def booking_reject_quote(request, pk):
    booking = get_object_or_404(Booking.objects.select_related('center'), pk=pk, user=request.user)
    if booking.status != Booking.STATUS_QUOTED:
        messages.info(request, 'Această ofertă nu mai așteaptă răspunsul tău.')
        return redirect('bookings:my_bookings')

    transition_booking_status(booking, Booking.STATUS_CANCELLED, actor=request.user)
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
            title=f'Clientul a refuzat propunerea pentru cererea #{booking.pk}',
            message=f'{booking.client_name} a refuzat oferta trimisă de service.',
        )
    messages.info(request, 'Ai refuzat propunerea pentru aceasta cerere.')
    return redirect('bookings:my_bookings')
