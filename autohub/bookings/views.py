from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from accounts.models import Car
from services.models import ServiceCenter, ServiceGarage
from .forms import BookingForm
from .models import Booking, BookingAttachment


def booking_create(request, slug):
    center = get_object_or_404(ServiceCenter.objects.prefetch_related('garages'), slug=slug, is_active=True)

    if request.method == 'POST':
        form = BookingForm(center=center, user=request.user, data=request.POST, files=request.FILES)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.center = center
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

    slots = garage.available_slots_for_date(booking_date)
    return JsonResponse({
        'garage': garage.name,
        'open_time': garage.open_time.strftime('%H:%M'),
        'close_time': garage.close_time.strftime('%H:%M'),
        'slot_minutes': garage.slot_minutes,
        'slots': slots,
    })
