from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Avg, Count, Min, Max, Q, Prefetch, F, Subquery, OuterRef
from django.utils import timezone

from .models import ServiceCategory, ServiceCenter, ServiceItem, Review, Favorite, ServiceGarage, ServiceImage, ServiceMechanic, ReviewImage
from .forms import (
    ServiceCenterRegisterForm,
    ServiceCenterPublicRegisterForm,
    ServiceGarageForm,
    ServiceGalleryImageForm,
    ServiceMechanicForm,
    ServiceOwnerBookingForm,
    ReviewForm,
)
from bookings.models import Booking, BookingNotification, BookingAttachment


def category_list(request):
    categories = ServiceCategory.objects.all().order_by('order')
    for cat in categories:
        cat.center_count_display = ServiceCenter.objects.filter(
            Q(category=cat) | Q(categories=cat),
            is_active=True
        ).distinct().count()
    return render(request, 'services/categories.html', {'categories': categories})


def service_list(request):
    category_slug = request.GET.get('category', '').strip()
    city = request.GET.get('city', '').strip()
    min_rating = request.GET.get('min_rating', '').strip()
    price_min = request.GET.get('price_min', '').strip()
    price_max = request.GET.get('price_max', '').strip()
    sort_by = request.GET.get('sort', 'rating')
    search_q = request.GET.get('q', '').strip()

    qs = ServiceCenter.objects.filter(is_active=True).prefetch_related(
        'categories', 'serviceitem_set', 'review_set'
    ).select_related('category')

    if search_q:
        search_q_lower = search_q.lower()
        matched_category = ServiceCategory.objects.filter(
            Q(name__iexact=search_q) |
            Q(name__icontains=search_q) |
            Q(slug__iexact=search_q_lower.replace(' ', '-'))
        ).first()
        if matched_category:
            qs = qs.filter(
                Q(categories=matched_category) | Q(category=matched_category)
            ).distinct()
        else:
            qs = qs.filter(
                Q(name__icontains=search_q) |
                Q(description__icontains=search_q) |
                Q(address__icontains=search_q) |
                Q(categories__name__icontains=search_q) |
                Q(category__name__icontains=search_q)
            ).distinct()

    if category_slug:
        qs = qs.filter(
            Q(categories__slug=category_slug) | Q(category__slug=category_slug)
        ).distinct()

    if city:
        qs = qs.filter(city=city)

    # Calcul in Python - imun la distinct()
    centers = list(qs)

    for c in centers:
        approved = [r for r in c.review_set.all() if r.is_approved]
        c.avg_rating = round(sum(r.rating for r in approved) / len(approved), 1) if approved else 0.0
        c.review_count = len(approved)
        prices = [float(s.price_from) for s in c.serviceitem_set.all() if s.price_from is not None]
        c.min_price = min(prices) if prices else None

    # Filtrare dupa rating
    if min_rating:
        try:
            r_val = float(min_rating)
            centers = [c for c in centers if c.avg_rating >= r_val]
        except ValueError:
            pass

    # Filtrare dupa pret
    if price_min:
        try:
            p = float(price_min)
            centers = [c for c in centers if c.min_price is not None and c.min_price >= p]
        except ValueError:
            pass

    if price_max:
        try:
            p = float(price_max)
            centers = [c for c in centers if c.min_price is not None and c.min_price <= p]
        except ValueError:
            pass

    # Sortare in Python - 100% corecta
    if sort_by == 'price_asc':
        centers.sort(key=lambda c: (c.min_price is None, c.min_price or 0))
    elif sort_by == 'price_desc':
        centers.sort(key=lambda c: (c.min_price is None, -(c.min_price or 0)))
    elif sort_by == 'reviews':
        centers.sort(key=lambda c: -c.review_count)
    elif sort_by == 'name':
        centers.sort(key=lambda c: c.name.lower())
    else:  # rating
        centers.sort(key=lambda c: (-c.avg_rating, -c.review_count))

    categories = ServiceCategory.objects.all()
    from .models import CITY_CHOICES
    context = {
        'centers': centers,
        'top5': centers[:5],
        'categories': categories,
        'cities': CITY_CHOICES,
        'selected_category': category_slug,
        'selected_city': city,
        'selected_min_rating': min_rating,
        'selected_price_min': price_min,
        'selected_price_max': price_max,
        'selected_sort': sort_by,
        'search_q': search_q,
        'total_count': len(centers),
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

    can_review = False
    user_review = None
    review_form = ReviewForm()
    if request.user.is_authenticated:
        can_review = Booking.objects.filter(
            user=request.user, center=center, status=Booking.STATUS_DONE
        ).exists()
        user_review = Review.objects.filter(center=center, user=request.user).first()

    return render(request, 'services/service_detail.html', {
        'center': center,
        'services': services,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'review_count': review_count,
        'is_favorited': is_favorited,
        'rating_breakdown': rating_breakdown,
        'popular_services': services.filter(is_popular=True)[:3],
        'can_review': can_review,
        'user_review': user_review,
        'review_form': review_form,
    })


@login_required
def review_create(request, slug):
    center = get_object_or_404(ServiceCenter, slug=slug, is_active=True)
    from bookings.models import Booking

    has_done_booking = Booking.objects.filter(user=request.user, center=center, status=Booking.STATUS_DONE).exists()
    if not has_done_booking:
        messages.error(request, 'Poți lăsa o recenzie doar după o programare finalizată.')
        return redirect(center.get_absolute_url())

    if Review.objects.filter(center=center, user=request.user).exists():
        messages.info(request, 'Ai lăsat deja o recenzie pentru acest service.')
        return redirect(center.get_absolute_url())

    if request.method != 'POST':
        return redirect(center.get_absolute_url())

    form = ReviewForm(request.POST, request.FILES)
    if form.is_valid():
        review = form.save(commit=False)
        review.center = center
        review.user = request.user
        review.full_clean()
        review.save()
        for image in request.FILES.getlist('images'):
            ReviewImage.objects.create(review=review, image=image)
        messages.success(request, 'Recenzia a fost adăugată cu succes.')
    else:
        messages.error(request, 'Recenzia nu a putut fi salvată. Verifică datele introduse.')
    return redirect(center.get_absolute_url())


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
            # ===== DEBUG TEMPORAR =====
            print("=" * 60)
            print("FORM PUBLIC ERRORS:", form.errors)
            print("POST DATA:", request.POST)
            print("=" * 60)
    else:
        form = ServiceCenterPublicRegisterForm()
    return render(request, 'services/service_register_public.html', {'form': form})


@login_required
def service_register(request):
    if request.method == 'POST':
        form = ServiceCenterRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            center = form.save(commit=True)
            center.owner = request.user
            center.save(update_fields=['owner'])
            if center.verification_status == 'pending':
                messages.info(request, '✅ Service-ul a fost înregistrat, dar este în așteptare pentru verificare (date legale completate).')
            else:
                messages.success(request, '✅ Service-ul a fost înregistrat. Acum poți gestiona programările din dashboard.')
            return redirect('services:dashboard')
        else:
            # ===== DEBUG TEMPORAR =====
            print("=" * 60)
            print("FORM REGISTER ERRORS:", form.errors)
            print("POST DATA:", request.POST)
            print("=" * 60)
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

    bookings_qs = Booking.objects.filter(center__in=centers).select_related('center', 'service_item', 'user', 'garage', 'mechanic').prefetch_related('attachments').order_by('-created_at')
    pending = bookings_qs.filter(status=Booking.STATUS_PENDING)
    active = bookings_qs.exclude(status=Booking.STATUS_CANCELLED)[:50]
    unread_count = BookingNotification.objects.filter(recipient=request.user, is_read=False).count()
    latest_notifications = BookingNotification.objects.filter(recipient=request.user)[:6]
    pending_verifications = ServiceCenter.objects.filter(verification_status='pending').count() if request.user.is_staff else 0
    mechanic_form = ServiceMechanicForm(prefix='mechanic')
    mechanics_by_center = [(center, center.mechanics.order_by('name')) for center in centers]

    return render(request, 'services/service_dashboard.html', {
        'centers': centers,
        'pending_bookings': pending,
        'bookings': active,
        'unread_count': unread_count,
        'latest_notifications': latest_notifications,
        'pending_verifications': pending_verifications,
        'mechanic_form': mechanic_form,
        'mechanics_by_center': mechanics_by_center,
    })


@login_required
def mechanic_create(request, pk):
    center = _owner_center_or_404(request, pk)
    if center is None:
        return redirect('core:home')

    if request.method == 'POST':
        form = ServiceMechanicForm(request.POST, prefix='mechanic')
        if form.is_valid():
            mechanic = form.save(commit=False)
            mechanic.center = center
            mechanic.save()
            messages.success(request, f'Mecanicul {mechanic.name} a fost adăugat.')
        else:
            messages.error(request, 'Mecanicul nu a putut fi salvat. Verifică datele introduse.')
    return redirect('services:dashboard')



@login_required
def mechanic_update(request, pk):
    mechanic = get_object_or_404(ServiceMechanic, pk=pk)
    if not (request.user.is_staff or mechanic.center.owner_id == request.user.id):
        return redirect('core:home')

    if request.method == 'POST':
        form = ServiceMechanicForm(request.POST, instance=mechanic, prefix=f'mech_{mechanic.pk}')
        if form.is_valid():
            form.save()
            messages.success(request, f'Datele mecanicului {mechanic.name} au fost actualizate.')
        else:
            messages.error(request, 'Datele mecanicului nu au putut fi salvate. Verifică formularul.')
    return redirect('services:dashboard')


@login_required
def mechanic_delete(request, pk):
    mechanic = get_object_or_404(ServiceMechanic, pk=pk)
    if not (request.user.is_staff or mechanic.center.owner_id == request.user.id):
        return redirect('core:home')

    if request.method == 'POST':
        name = mechanic.name
        mechanic.delete()
        messages.success(request, f'Mecanicul {name} a fost șters.')
    return redirect('services:dashboard')


@login_required
def booking_detail(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('center', 'service_item', 'user', 'garage', 'mechanic').prefetch_related('attachments'),
        pk=pk,
    )
    if not (request.user.is_staff or booking.center.owner_id == request.user.id):
        return redirect('core:home')

    mechanics = booking.center.mechanics.order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_work_order_info':
            booking.used_services = (request.POST.get('used_services') or '').strip()
            booking.additional_description = (request.POST.get('additional_description') or '').strip()
            booking.save(update_fields=['used_services', 'additional_description', 'updated_at'])
            messages.success(request, 'Detaliile suplimentare pentru fișa de comandă au fost salvate.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'assign_mechanic':
            mechanic_id = (request.POST.get('mechanic') or '').strip()
            mechanic = None
            if mechanic_id:
                mechanic = get_object_or_404(ServiceMechanic, pk=mechanic_id, center=booking.center)
            booking.mechanic = mechanic
            booking.save(update_fields=['mechanic', 'updated_at'])
            messages.success(request, 'Mecanicul a fost actualizat pentru această programare.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'delete_attachment':
            attachment_id = (request.POST.get('attachment_id') or '').strip()
            attachment = get_object_or_404(BookingAttachment, pk=attachment_id, booking=booking)
            file_storage = attachment.file
            attachment.delete()
            if file_storage:
                file_storage.delete(save=False)
            messages.info(request, 'Fișierul a fost șters din programare.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'add_attachments':
            files = request.FILES.getlist('attachments')
            if not files:
                messages.warning(request, 'Selectează cel puțin o poză sau un video.')
                return redirect('services:booking_detail', pk=booking.pk)

            added = 0
            for uploaded in files:
                content_type = getattr(uploaded, 'content_type', '') or ''
                if not (content_type.startswith('image/') or content_type.startswith('video/')):
                    continue
                media_kind = 'video' if content_type.startswith('video/') else 'image'
                BookingAttachment.objects.create(booking=booking, file=uploaded, media_kind=media_kind)
                added += 1

            if added:
                messages.success(request, f'Au fost adăugate {added} fișiere la programare.')
            else:
                messages.error(request, 'Fișierele selectate nu sunt imagini sau video valide.')
            return redirect('services:booking_detail', pk=booking.pk)

    return render(request, 'services/booking_detail.html', {
        'booking': booking,
        'mechanics': mechanics,
    })


@login_required
def booking_print(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('center', 'service_item', 'user', 'garage', 'mechanic'),
        pk=pk,
    )
    if not (request.user.is_staff or booking.center.owner_id == request.user.id):
        return redirect('core:home')

    return render(request, 'services/booking_print.html', {'booking': booking})


@login_required
def owner_booking_create(request, pk):
    center = _owner_center_or_404(request, pk)
    if center is None:
        return redirect('core:home')

    if request.method == 'POST':
        form = ServiceOwnerBookingForm(center=center, user=request.user, data=request.POST, files=request.FILES)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.center = center
            booking.status = Booking.STATUS_CONFIRMED
            booking.duration_minutes = form.cleaned_data['duration_minutes']
            saved_car = form.cleaned_data.get('saved_car')
            if saved_car:
                booking.user = saved_car.owner
            booking.full_clean()
            booking.save()

            for uploaded in request.FILES.getlist('attachments'):
                content_type = getattr(uploaded, 'content_type', '') or ''
                media_kind = 'video' if content_type.startswith('video/') else 'image'
                BookingAttachment.objects.create(booking=booking, file=uploaded, media_kind=media_kind)

            if booking.user:
                BookingNotification.objects.create(
                    recipient=booking.user,
                    booking=booking,
                    kind=BookingNotification.KIND_STATUS_UPDATE,
                    title=f"Service-ul a înregistrat programarea #{booking.pk} ✅",
                    message=(
                        f"{booking.center.name} a înregistrat direct o programare pentru {booking.booking_date} la "
                        f"{booking.booking_time.strftime('%H:%M')} în {booking.garage.name if booking.garage_id else 'service'}."
                    ),
                )

            messages.success(request, f'✅ Programarea #{booking.pk} a fost adăugată direct și confirmată.')
            return redirect('services:dashboard')
    else:
        form = ServiceOwnerBookingForm(center=center, user=request.user)

    cars = form.fields['saved_car'].queryset
    return render(request, 'services/owner_booking_create.html', {
        'center': center,
        'form': form,
        'cars': cars,
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

        raw_duration = (request.POST.get('duration_minutes') or '').strip()
        if not raw_duration:
            messages.error(request, 'Selectează durata care blochează garajul înainte să accepți programarea.')
            return redirect('services:dashboard')
        try:
            duration_minutes = int(raw_duration)
        except ValueError:
            messages.error(request, 'Durata selectată nu este validă.')
            return redirect('services:dashboard')

        allowed_durations = {30 * step for step in range(1, 17)}
        if duration_minutes not in allowed_durations:
            messages.error(request, 'Durata trebuie să fie selectată din 30 în 30 de minute.')
            return redirect('services:dashboard')

        if booking.garage_id and not booking.garage.is_time_available(
            booking.booking_date,
            booking.booking_time,
            duration_minutes=duration_minutes,
            exclude_booking_id=booking.pk,
            booking_status=Booking.STATUS_CONFIRMED,
        ):
            messages.error(request, 'Garajul nu mai este disponibil pe tot intervalul selectat.')
            return redirect('services:dashboard')

        booking.status = Booking.STATUS_CONFIRMED
        booking.duration_minutes = duration_minutes
        booking.save(update_fields=['status', 'duration_minutes', 'updated_at'])
        if booking.user:
            BookingNotification.objects.create(
                recipient=booking.user,
                booking=booking,
                kind=BookingNotification.KIND_STATUS_UPDATE,
                title=f"Programarea #{booking.pk} a fost acceptată ✅",
                message=(
                    f"Service-ul {booking.center.name} ți-a confirmat programarea pentru {booking.booking_date} la "
                    f"{booking.booking_time.strftime('%H:%M')} și a rezervat garajul pentru {booking.get_duration_display()}."
                ),
            )
        messages.success(request, f'✅ Ai acceptat programarea #{booking.pk} pentru {booking.get_duration_display()}.')
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