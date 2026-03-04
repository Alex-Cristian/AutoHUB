from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from services.models import ServiceCenter
from .models import Booking
from .forms import BookingForm

from accounts.models import Car


def booking_create(request, slug):
    center = get_object_or_404(ServiceCenter, slug=slug, is_active=True)

    if request.method == 'POST':
        form = BookingForm(center=center, user=request.user, data=request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.center = center
            if request.user.is_authenticated:
                booking.user = request.user
            booking.full_clean()  # Run model-level validation too
            booking.save()
            messages.success(
                request,
                f'✅ Programare confirmată! Vă așteptăm pe {booking.booking_date.strftime("%d %B %Y")} la ora {booking.booking_time.strftime("%H:%M")}.'
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
    booking = get_object_or_404(Booking, pk=pk)
    # Security: only owner or guest (no user) can see confirmation
    if booking.user and request.user != booking.user and not request.user.is_staff:
        return redirect('core:home')
    return render(request, 'bookings/booking_success.html', {'booking': booking})


@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).select_related(
        'center', 'center__category', 'service_item'
    ).order_by('-created_at')
    return render(request, 'bookings/my_bookings.html', {'bookings': bookings})
