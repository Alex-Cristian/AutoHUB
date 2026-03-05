from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Min, Max, Q
from .models import ServiceCategory, ServiceCenter, ServiceItem, Review, Favorite
<<<<<<< HEAD
=======
from .forms import ServiceCenterRegisterForm

from bookings.models import Booking, BookingNotification
>>>>>>> origin/main


def category_list(request):
    categories = ServiceCategory.objects.annotate(
        center_count=Count(
            'servicecenter',
            filter=Q(servicecenter__is_active=True)
        )
    ).order_by('order')
    return render(request, 'services/categories.html', {'categories': categories})


def service_list(request):
    qs = ServiceCenter.objects.filter(is_active=True).annotate(
        avg_rating=Avg('review__rating', filter=Q(review__is_approved=True)),
        review_count=Count('review', filter=Q(review__is_approved=True)),
        # ServiceItem.center folosește related_name='serviceitem_set'
        # deci relația inversă în ORM este serviceitem_set (nu serviceitem).
        min_price=Min('serviceitem_set__price_from'),
        max_price=Max('serviceitem_set__price_to'),
    )

    # --- Filtre ---
    category_slug = request.GET.get('category', '').strip()
    city = request.GET.get('city', '').strip()
    min_rating = request.GET.get('min_rating', '').strip()
    price_min = request.GET.get('price_min', '').strip()
    price_max = request.GET.get('price_max', '').strip()
    sort_by = request.GET.get('sort', 'rating')
    search_q = request.GET.get('q', '').strip()

    if search_q:
        qs = qs.filter(
            Q(name__icontains=search_q) |
            Q(description__icontains=search_q) |
            Q(address__icontains=search_q)
        )

    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    if city:
        qs = qs.filter(city=city)

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

    # --- Sortare ---
    sort_options = {
        'rating': '-avg_rating',
        'price_asc': 'min_price',
        'price_desc': '-min_price',
        'reviews': '-review_count',
        'name': 'name',
    }
    qs = qs.order_by(sort_options.get(sort_by, '-avg_rating'))

    # Top 5 pentru "harta" placeholder
    top5 = qs[:5]

    categories = ServiceCategory.objects.all()
    from .models import CITY_CHOICES
    cities = CITY_CHOICES

    context = {
        'centers': qs,
        'top5': top5,
        'categories': categories,
        'cities': cities,
        'selected_category': category_slug,
        'selected_city': city,
        'selected_min_rating': min_rating,
        'selected_price_min': price_min,
        'selected_price_max': price_max,
        'selected_sort': sort_by,
        'search_q': search_q,
        'total_count': qs.count(),
    }
    return render(request, 'services/service_list.html', context)


def service_detail(request, slug):
    center = get_object_or_404(ServiceCenter, slug=slug, is_active=True)
    services = center.serviceitem_set.all()
    reviews = center.review_set.filter(is_approved=True).select_related('user')
    avg_rating = center.avg_rating()
    review_count = center.review_count()
    is_favorited = center.is_favorited_by(request.user)

    # Rating breakdown
    rating_breakdown = {}
    for i in range(5, 0, -1):
        cnt = reviews.filter(rating=i).count()
        pct = int((cnt / review_count * 100)) if review_count else 0
        rating_breakdown[i] = {'count': cnt, 'pct': pct}

    context = {
        'center': center,
        'services': services,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'review_count': review_count,
        'is_favorited': is_favorited,
        'rating_breakdown': rating_breakdown,
        'popular_services': services.filter(is_popular=True)[:3],
    }
    return render(request, 'services/service_detail.html', context)


@login_required
def toggle_favorite(request, slug):
    center = get_object_or_404(ServiceCenter, slug=slug)
    fav, created = Favorite.objects.get_or_create(user=request.user, center=center)
    if not created:
        fav.delete()
        messages.info(request, f'"{center.name}" a fost eliminat din favorite.')
    else:
        messages.success(request, f'"{center.name}" a fost adăugat la favorite!')
    return redirect(request.META.get('HTTP_REFERER', center.get_absolute_url()))
<<<<<<< HEAD
=======


@login_required
def service_register(request):
    """Register a new service center owned by the current user."""
    if request.method == 'POST':
        form = ServiceCenterRegisterForm(request.POST)
        if form.is_valid():
            center = form.save(commit=False)
            center.owner = request.user
            center.is_active = True
            center.save()
            messages.success(request, '✅ Service-ul a fost înregistrat. Acum poți gestiona programările din dashboard.')
            return redirect('services:dashboard')
    else:
        form = ServiceCenterRegisterForm()

    return render(request, 'services/service_register.html', {
        'form': form,
        'existing_centers': ServiceCenter.objects.filter(owner=request.user).order_by('-created_at'),
    })


def _require_service_owner(request):
    centers = ServiceCenter.objects.filter(owner=request.user)
    if not centers.exists() and not request.user.is_staff:
        messages.info(request, 'Contul tău nu are încă un service înregistrat. Înregistrează unul ca să primești programări.')
        return None
    return centers


@login_required
def service_dashboard(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')

    # Bookings for all owned centers
    bookings_qs = Booking.objects.filter(center__in=centers).select_related(
        'center', 'service_item', 'user'
    ).order_by('-created_at')

    pending = bookings_qs.filter(status=Booking.STATUS_PENDING)
    active = bookings_qs.exclude(status=Booking.STATUS_CANCELLED)[:50]

    unread_count = BookingNotification.objects.filter(recipient=request.user, is_read=False).count()
    latest_notifications = BookingNotification.objects.filter(recipient=request.user)[:6]

    return render(request, 'services/service_dashboard.html', {
        'centers': centers,
        'pending_bookings': pending,
        'bookings': active,
        'unread_count': unread_count,
        'latest_notifications': latest_notifications,
    })


@login_required
def booking_accept(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if not (request.user.is_staff or booking.center.owner_id == request.user.id):
        return redirect('core:home')

    if request.method == 'POST':
        if booking.status != Booking.STATUS_PENDING:
            messages.info(request, 'Această programare nu mai este în așteptare.')
            return redirect('services:dashboard')

        booking.status = Booking.STATUS_CONFIRMED
        booking.save(update_fields=['status', 'updated_at'])

        # Notify client (in-app if user exists)
        if booking.user:
            BookingNotification.objects.create(
                recipient=booking.user,
                booking=booking,
                kind=BookingNotification.KIND_STATUS_UPDATE,
                title=f"Programarea #{booking.pk} a fost acceptată ✅",
                message=f"Service-ul {booking.center.name} ți-a confirmat programarea pentru {booking.booking_date} la {booking.booking_time}.",
            )
        messages.success(request, f'✅ Ai acceptat programarea #{booking.pk}.')
    return redirect('services:dashboard')


@login_required
def booking_reject(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if not (request.user.is_staff or booking.center.owner_id == request.user.id):
        return redirect('core:home')

    if request.method == 'POST':
        if booking.status != Booking.STATUS_PENDING:
            messages.info(request, 'Această programare nu mai este în așteptare.')
            return redirect('services:dashboard')

        booking.status = Booking.STATUS_CANCELLED
        booking.save(update_fields=['status', 'updated_at'])

        if booking.user:
            BookingNotification.objects.create(
                recipient=booking.user,
                booking=booking,
                kind=BookingNotification.KIND_STATUS_UPDATE,
                title=f"Programarea #{booking.pk} a fost respinsă ❌",
                message=f"Din păcate, {booking.center.name} nu poate onora programarea pentru {booking.booking_date} la {booking.booking_time}.",
            )
        messages.warning(request, f'❌ Ai respins programarea #{booking.pk}.')
    return redirect('services:dashboard')


@login_required
def service_notifications(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')

    notifs = BookingNotification.objects.filter(recipient=request.user)
    return render(request, 'services/service_notifications.html', {
        'notifications': notifs,
    })


@login_required
def notification_mark_read(request, pk):
    notif = get_object_or_404(BookingNotification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return redirect(request.META.get('HTTP_REFERER', 'services:notifications'))
>>>>>>> origin/main
