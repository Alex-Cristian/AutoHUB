from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Avg, Count, Min, Max, Q, Prefetch
from django.utils import timezone

from .models import ServiceCategory, ServiceCenter, ServiceItem, Review, Favorite, ServiceGarage, ServiceImage
from .forms import (
    ServiceCenterRegisterForm,
    ServiceCenterPublicRegisterForm,
    ServiceGarageForm,
    ServiceGalleryImageForm,
)
from bookings.models import Booking, BookingNotification


def category_list(request):
    categories = ServiceCategory.objects.annotate(
        center_count=Count('center_categories', filter=Q(center_categories__is_active=True), distinct=True)
    ).order_by('order')
    return render(request, 'services/categories.html', {'categories': categories})


def service_list(request):
    qs = ServiceCenter.objects.filter(is_active=True).annotate(
        avg_rating=Avg('review__rating', filter=Q(review__is_approved=True)),
        review_count=Count('review', filter=Q(review__is_approved=True)),
        min_price=Min('serviceitem_set__price_from'),
        max_price=Max('serviceitem_set__price_to'),
    ).prefetch_related('categories')

    category_slug = request.GET.get('category', '').strip()
    city = request.GET.get('city', '').strip()
    min_rating = request.GET.get('min_rating', '').strip()
    price_min = request.GET.get('price_min', '').strip()
    price_max = request.GET.get('price_max', '').strip()
    sort_by = request.GET.get('sort', 'rating')
    search_q = request.GET.get('q', '').strip()

    if search_q:
        qs = qs.filter(Q(name__icontains=search_q) | Q(description__icontains=search_q) | Q(address__icontains=search_q))

    if category_slug:
        qs = qs.filter(Q(categories__slug=category_slug) | Q(category__slug=category_slug)).distinct()

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

    sort_options = {
        'rating': '-avg_rating',
        'price_asc': 'min_price',
        'price_desc': '-min_price',
        'reviews': '-review_count',
        'name': 'name',
    }
    qs = qs.order_by(sort_options.get(sort_by, '-avg_rating'))

    categories = ServiceCategory.objects.all()
    from .models import CITY_CHOICES
    context = {
        'centers': qs,
        'top5': qs[:5],
        'categories': categories,
        'cities': CITY_CHOICES,
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
    center = get_object_or_404(
        ServiceCenter.objects.prefetch_related('categories', 'garages', 'gallery_images', 'serviceitem_set'),
        slug=slug,
        is_active=True,
    )
    services = center.serviceitem_set.all()
    reviews = center.review_set.filter(is_approved=True).select_related('user')
    avg_rating = center.avg_rating()
    review_count = center.review_count()
    is_favorited = center.is_favorited_by(request.user)

    rating_breakdown = {}
    for i in range(5, 0, -1):
        cnt = reviews.filter(rating=i).count()
        pct = int((cnt / review_count * 100)) if review_count else 0
        rating_breakdown[i] = {'count': cnt, 'pct': pct}

    return render(request, 'services/service_detail.html', {
        'center': center,
        'services': services,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'review_count': review_count,
        'is_favorited': is_favorited,
        'rating_breakdown': rating_breakdown,
        'popular_services': services.filter(is_popular=True)[:3],
    })


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


def service_register_public(request):
    if request.method == 'POST':
        form = ServiceCenterPublicRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            center, user = form.save()
            login(request, user)
            if center.verification_status == 'pending':
                messages.info(request, '✅ Contul și service-ul au fost create. Service-ul este în așteptare pentru verificare (date legale completate).')
            else:
                messages.success(request, '✅ Contul și service-ul au fost create. Bine ai venit în dashboard!')
            return redirect('services:dashboard')
    else:
        form = ServiceCenterPublicRegisterForm()
    return render(request, 'services/service_register_public.html', {'form': form})


@login_required
def service_register(request):
    if request.method == 'POST':
        form = ServiceCenterRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            center = form.save(commit=False)
            center.owner = request.user
            center.save()
            form.instance = center
            form.save_m2m()
            if center.verification_status == 'pending':
                messages.info(request, '✅ Service-ul a fost înregistrat, dar este în așteptare pentru verificare (date legale completate).')
            else:
                messages.success(request, '✅ Service-ul a fost înregistrat. Acum poți gestiona programările din dashboard.')
            return redirect('services:dashboard')
    else:
        form = ServiceCenterRegisterForm()

    return render(request, 'services/service_register.html', {
        'form': form,
        'existing_centers': ServiceCenter.objects.filter(owner=request.user).prefetch_related('categories').order_by('-created_at'),
    })


def _staff_required(user):
    return user.is_staff


@user_passes_test(_staff_required)
def verification_list(request):
    pending = ServiceCenter.objects.filter(verification_status='pending').order_by('-created_at')
    return render(request, 'services/verification_list.html', {'pending_centers': pending})


@user_passes_test(_staff_required)
def verification_detail(request, pk):
    center = get_object_or_404(ServiceCenter, pk=pk)
    return render(request, 'services/verification_detail.html', {'center': center})


@user_passes_test(_staff_required)
def verification_approve(request, pk):
    center = get_object_or_404(ServiceCenter, pk=pk)
    if request.method == 'POST':
        center.verification_status = 'verified'
        center.is_active = True
        center.verified_at = timezone.now()
        center.verification_note = (request.POST.get('note') or '').strip()
        center.save()
        messages.success(request, f'✅ "{center.name}" a fost verificat și activat.')
        return redirect('services:verification_list')
    return redirect('services:verification_detail', pk=pk)


@user_passes_test(_staff_required)
def verification_reject(request, pk):
    center = get_object_or_404(ServiceCenter, pk=pk)
    if request.method == 'POST':
        center.verification_status = 'rejected'
        center.is_active = False
        center.verified_at = None
        center.verification_note = (request.POST.get('note') or '').strip()
        center.save()
        messages.warning(request, f'⛔ "{center.name}" a fost respins.')
        return redirect('services:verification_list')
    return redirect('services:verification_detail', pk=pk)


def _require_service_owner(request):
    centers = ServiceCenter.objects.filter(owner=request.user).prefetch_related('categories')
    if not centers.exists() and not request.user.is_staff:
        messages.info(request, 'Contul tău nu are încă un service înregistrat. Înregistrează unul ca să primești programări.')
        return None
    return centers


def _owner_center_or_404(request, pk):
    center = get_object_or_404(ServiceCenter.objects.prefetch_related('categories', 'garages', 'gallery_images'), pk=pk)
    if not (request.user.is_staff or center.owner_id == request.user.id):
        return None
    return center


@login_required
def service_dashboard(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')

    bookings_qs = Booking.objects.filter(center__in=centers).select_related('center', 'service_item', 'user').order_by('-created_at')
    pending = bookings_qs.filter(status=Booking.STATUS_PENDING)
    active = bookings_qs.exclude(status=Booking.STATUS_CANCELLED)[:50]
    unread_count = BookingNotification.objects.filter(recipient=request.user, is_read=False).count()
    latest_notifications = BookingNotification.objects.filter(recipient=request.user)[:6]
    pending_verifications = ServiceCenter.objects.filter(verification_status='pending').count() if request.user.is_staff else 0

    return render(request, 'services/service_dashboard.html', {
        'centers': centers,
        'pending_bookings': pending,
        'bookings': active,
        'unread_count': unread_count,
        'latest_notifications': latest_notifications,
        'pending_verifications': pending_verifications,
    })


@login_required
def service_profile_manage(request, pk):
    center = _owner_center_or_404(request, pk)
    if center is None:
        return redirect('core:home')

    profile_form = ServiceCenterRegisterForm(request.POST or None, request.FILES or None, instance=center, prefix='profile')
    garage_form = ServiceGarageForm(request.POST or None, center=center, prefix='garage')
    image_form = ServiceGalleryImageForm(request.POST or None, request.FILES or None, prefix='gallery')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profilul service-ului a fost actualizat.')
                return redirect('services:manage_profile', pk=center.pk)
        elif action == 'add_garage':
            if garage_form.is_valid():
                garage = garage_form.save(commit=False)
                garage.center = center
                garage.save()
                messages.success(request, 'Garajul a fost adăugat.')
                return redirect('services:manage_profile', pk=center.pk)
        elif action == 'add_gallery_image':
            if image_form.is_valid():
                image = image_form.save(commit=False)
                image.center = center
                image.save()
                messages.success(request, 'Poza a fost adăugată în galerie.')
                return redirect('services:manage_profile', pk=center.pk)

    return render(request, 'services/service_profile_manage.html', {
        'center': center,
        'profile_form': profile_form,
        'garage_form': garage_form,
        'image_form': image_form,
    })


@login_required
def garage_delete(request, pk):
    garage = get_object_or_404(ServiceGarage.objects.select_related('center'), pk=pk)
    if not (request.user.is_staff or garage.center.owner_id == request.user.id):
        return redirect('core:home')
    if request.method == 'POST':
        center_pk = garage.center_id
        garage.delete()
        messages.info(request, 'Garajul a fost șters.')
        return redirect('services:manage_profile', pk=center_pk)
    return redirect('services:dashboard')


@login_required
def gallery_image_delete(request, pk):
    image = get_object_or_404(ServiceImage.objects.select_related('center'), pk=pk)
    if not (request.user.is_staff or image.center.owner_id == request.user.id):
        return redirect('core:home')
    if request.method == 'POST':
        center_pk = image.center_id
        image.delete()
        messages.info(request, 'Poza a fost ștearsă.')
        return redirect('services:manage_profile', pk=center_pk)
    return redirect('services:dashboard')


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
    return render(request, 'services/service_notifications.html', {'notifications': notifs})


@login_required
def notification_mark_read(request, pk):
    notif = get_object_or_404(BookingNotification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return redirect(request.META.get('HTTP_REFERER', 'services:notifications'))
