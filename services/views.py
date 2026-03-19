from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import login
from django.db import models
from django.db.models import Avg, Count, Min, Max, Q, Prefetch
from django.utils import timezone
from django.urls import reverse

from .models import ServiceCategory, ServiceCenter, ServiceItem, Review, Favorite, ServiceGarage, ServiceImage, ServiceMechanic, ReviewImage, ServicePart
from .forms import (
    ServiceCenterRegisterForm,
    ServiceCenterPublicRegisterForm,
    ServiceGarageForm,
    ServiceGalleryImageForm,
    ServiceMechanicForm,
    ServiceOwnerBookingForm,
    ReviewForm,
    ServicePartForm,
)
from bookings.models import Booking, BookingNotification, BookingAttachment
from core.pdf_utils import build_work_order_pdf
from accounts.views import _record_legal_acceptance
from core.services.sms_service import (
    send_booking_completed_sms,
    send_booking_confirmation_sms,
    send_booking_started_sms,
)


def _post_redirect(request, fallback):
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect(fallback)


def category_list(request):
    categories = ServiceCategory.objects.all().order_by('order')
    for cat in categories:
        cat.center_count_display = ServiceCenter.objects.filter(
            Q(category=cat) | Q(categories=cat),
            is_active=True
        ).distinct().count()
    return render(request, 'services/categories.html', {'categories': categories})


def service_list(request):
    from django.db.models import Subquery, OuterRef, FloatField, IntegerField
    from django.db.models.functions import Coalesce

    min_price_sq = Subquery(
        ServiceItem.objects.filter(center=OuterRef('pk'))
        .order_by('price_from').values('price_from')[:1]
    )

    qs = ServiceCenter.objects.filter(is_active=True).annotate(
        avg_rating=Avg('review__rating', filter=Q(review__is_approved=True)),
        review_count=Count('review', filter=Q(review__is_approved=True), distinct=True),
        min_price=min_price_sq,
    ).prefetch_related('categories')

    category_slug = request.GET.get('category', '').strip()
    city = request.GET.get('city', '').strip()
    min_rating = request.GET.get('min_rating', '').strip()
    price_min = request.GET.get('price_min', '').strip()
    price_max = request.GET.get('price_max', '').strip()
    sort_by = request.GET.get('sort', 'rating')
    search_q = request.GET.get('q', '').strip()

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
                Q(categories__slug__icontains=search_q) |
                Q(category__name__icontains=search_q) |
                Q(category__slug__icontains=search_q)
            ).distinct()

    if category_slug:
        qs = qs.filter(
            Q(categories__slug=category_slug) | Q(category__slug=category_slug)
        ).distinct()

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

    from django.db.models import F
    sort_options = {
        'rating': F('avg_rating').desc(nulls_last=True),
        'price_asc': F('min_price').asc(nulls_last=True),
        'price_desc': F('min_price').desc(nulls_last=True),
        'reviews': F('review_count').desc(nulls_last=True),
        'name': F('name').asc(),
    }
    qs = qs.order_by(sort_options.get(sort_by, F('avg_rating').desc(nulls_last=True)))

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

    can_review = False
    user_review = None
    review_form = ReviewForm()
    if request.user.is_authenticated:
        from bookings.models import Booking
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
            _record_legal_acceptance(user, request)
            login(request, user)
            if center.verification_status == 'pending':
                messages.info(request, '✅ Contul și service-ul au fost create. Service-ul este în așteptare pentru verificare (date legale completate).')
            else:
                messages.success(request, '✅ Contul și service-ul au fost create. Bine ai venit în dashboard!')
            return _post_redirect(request, 'services:dashboard')
        else:
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
            return _post_redirect(request, 'services:dashboard')
        else:
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
    centers = centers.prefetch_related('garages', 'garages__category', 'categories')

    bookings_qs = Booking.objects.filter(center__in=centers).select_related('center', 'service_item', 'user', 'garage', 'mechanic').prefetch_related('attachments').order_by('-created_at')
    pending = bookings_qs.filter(status=Booking.STATUS_PENDING)
    active = bookings_qs.exclude(status=Booking.STATUS_CANCELLED)[:50]
    unread_count = BookingNotification.objects.filter(recipient=request.user, is_read=False).count()
    latest_notifications = BookingNotification.objects.filter(recipient=request.user)[:6]
    pending_verifications = ServiceCenter.objects.filter(verification_status='pending').count() if request.user.is_staff else 0
    mechanic_form = ServiceMechanicForm()
    mechanics_by_center = [(center, center.mechanics.order_by('name')) for center in centers]

    low_stock_count = ServicePart.objects.filter(center__in=centers, stock__lte=models.F('minimum_stock')).count()

    return render(request, 'services/service_dashboard.html', {
        'centers': centers,
        'pending_bookings': pending,
        'bookings': active,
        'unread_count': unread_count,
        'latest_notifications': latest_notifications,
        'pending_verifications': pending_verifications,
        'mechanic_form': mechanic_form,
        'mechanics_by_center': mechanics_by_center,
        'low_stock_count': low_stock_count,
    })


@login_required
def bookings_list(request):
    """Pagina dedicată cu toate programările — search live + filtre pe status."""
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')
    centers = centers.prefetch_related('garages', 'categories')

    bookings = Booking.objects.filter(
        center__in=centers
    ).select_related(
        'center', 'garage', 'mechanic'
    ).order_by('-booking_date', '-booking_time')

    return render(request, 'services/bookings_list.html', {
        'bookings': bookings,
        'centers': centers,
    })


@login_required
def mechanic_create(request, pk):
    center = _owner_center_or_404(request, pk)
    if center is None:
        return redirect('core:home')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            from .models import ServiceGarage, ServiceCategory
            mechanic = ServiceMechanic(center=center, name=name)
            mechanic.specialization = request.POST.get('specialization', '').strip()
            mechanic.phone = request.POST.get('phone', '').strip()
            mechanic.email = request.POST.get('email', '').strip()
            garage_id = request.POST.get('garage', '').strip()
            if garage_id:
                try:
                    mechanic.garage = ServiceGarage.objects.get(pk=garage_id, center=center)
                except ServiceGarage.DoesNotExist:
                    pass
            if request.FILES.get('photo'):
                mechanic.photo = request.FILES['photo']
            mechanic.save()
            cat_ids = request.POST.getlist('service_categories')
            if cat_ids:
                mechanic.service_categories.set(ServiceCategory.objects.filter(pk__in=cat_ids))
            messages.success(request, f'Mecanicul {mechanic.name} a fost adăugat.')
        else:
            messages.error(request, 'Numele mecanicului este obligatoriu.')
    referer = request.META.get('HTTP_REFERER', '')
    if 'mechanici' in referer:
        return redirect('services:mechanics_list')
    return _post_redirect(request, 'services:dashboard')


@login_required
def mechanic_update(request, pk):
    mechanic = get_object_or_404(ServiceMechanic, pk=pk)
    if not (request.user.is_staff or mechanic.center.owner_id == request.user.id):
        return redirect('core:home')

    if request.method == 'POST':
        # Salvare directă din câmpurile trimise de modal
        name = request.POST.get('name', '').strip()
        if name:
            mechanic.name = name
        mechanic.specialization = request.POST.get('specialization', '').strip()
        mechanic.phone = request.POST.get('phone', '').strip()
        mechanic.email = request.POST.get('email', '').strip()

        # Garaj
        garage_id = request.POST.get('garage', '').strip()
        if garage_id:
            try:
                from .models import ServiceGarage
                mechanic.garage = ServiceGarage.objects.get(pk=garage_id, center=mechanic.center)
            except ServiceGarage.DoesNotExist:
                mechanic.garage = None
        else:
            mechanic.garage = None

        # Status disponibilitate (concediu etc.)
        availability_status = request.POST.get('availability_status', 'available')
        if hasattr(mechanic, 'availability_status'):
            mechanic.availability_status = availability_status

        # Fotografie
        if request.FILES.get('photo'):
            mechanic.photo = request.FILES['photo']

        mechanic.save()

        # Categorii servicii
        cat_ids = request.POST.getlist('service_categories')
        from .models import ServiceCategory
        mechanic.service_categories.set(ServiceCategory.objects.filter(pk__in=cat_ids))

        messages.success(request, f'Datele mecanicului {mechanic.name} au fost actualizate.')

    # Întoarce la profilul mecanicului, nu la dashboard
    return redirect('services:mechanic_profile', pk=pk)


@login_required
def mechanic_delete(request, pk):
    mechanic = get_object_or_404(ServiceMechanic, pk=pk)
    if not (request.user.is_staff or mechanic.center.owner_id == request.user.id):
        return redirect('core:home')

    if request.method == 'POST':
        name = mechanic.name
        mechanic.delete()
        messages.success(request, f'Mecanicul {name} a fost șters.')
    return _post_redirect(request, 'services:dashboard')


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
            if mechanic and booking.user:
                BookingNotification.objects.create(
                    recipient=booking.user,
                    booking=booking,
                    kind=BookingNotification.KIND_STATUS_UPDATE,
                    title=f"Programarea #{booking.pk} a fost alocată unui mecanic",
                    message=f"{booking.center.name}: mecanicul {mechanic.name} va prelua mașina ta pe {booking.booking_date} la {booking.booking_time.strftime('%H:%M')}.",
                )
            messages.success(request, f'Mecanicul {"a fost alocat" if mechanic else "a fost eliminat"} pentru această programare.')
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

        if action == 'update_status':
            new_status = (request.POST.get('status') or '').strip()
            allowed_statuses = {choice[0] for choice in Booking.STATUS_CHOICES} - {Booking.STATUS_PENDING, Booking.STATUS_CANCELLED, Booking.STATUS_QUOTED}
            if new_status not in allowed_statuses:
                messages.error(request, 'Statusul selectat nu este valid.')
                return redirect('services:booking_detail', pk=booking.pk)
            booking.status = new_status
            booking.save(update_fields=['status', 'updated_at'])
            messages.success(request, f'Statusul programării a fost actualizat la „{booking.get_status_display()}”.')
            return redirect('services:booking_detail', pk=booking.pk)

    history_entries = Booking.objects.filter(
        center=booking.center,
        car_vin=booking.car_vin,
        status=Booking.STATUS_DONE,
    ).select_related('center').exclude(pk=booking.pk).order_by('-booking_date', '-booking_time', '-created_at')

    return render(request, 'services/booking_detail.html', {
        'booking': booking,
        'mechanics': mechanics,
        'history_entries': history_entries,
        'status_choices': [choice for choice in Booking.STATUS_CHOICES if choice[0] not in [Booking.STATUS_PENDING, Booking.STATUS_QUOTED, Booking.STATUS_CANCELLED]],
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

            sms_sent = send_booking_confirmation_sms(booking)
            if sms_sent:
                messages.success(request, f'✅ Programarea #{booking.pk} a fost adăugată direct, confirmată și notificată prin SMS.')
            else:
                messages.success(request, f'✅ Programarea #{booking.pk} a fost adăugată direct și confirmată.')
            return _post_redirect(request, 'services:dashboard')
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
            return _post_redirect(request, 'services:dashboard')

        raw_duration = (request.POST.get('duration_minutes') or '').strip()
        raw_price = (request.POST.get('estimated_price') or '').strip().replace(',', '.')
        if not raw_duration:
            messages.error(request, 'Selectează durata înainte să trimiți oferta către client.')
            return _post_redirect(request, 'services:dashboard')
        if not raw_price:
            messages.error(request, 'Completează și un preț aproximativ înainte să trimiți oferta către client.')
            return _post_redirect(request, 'services:dashboard')
        try:
            duration_minutes = int(raw_duration)
        except ValueError:
            messages.error(request, 'Durata selectată nu este validă.')
            return _post_redirect(request, 'services:dashboard')
        try:
            estimated_price = float(raw_price)
        except ValueError:
            messages.error(request, 'Prețul aproximativ nu este valid.')
            return _post_redirect(request, 'services:dashboard')

        allowed_durations = {30 * step for step in range(1, 17)}
        if duration_minutes not in allowed_durations:
            messages.error(request, 'Durata trebuie să fie selectată din 30 în 30 de minute.')
            return _post_redirect(request, 'services:dashboard')
        if estimated_price < 0:
            messages.error(request, 'Prețul aproximativ nu poate fi negativ.')
            return _post_redirect(request, 'services:dashboard')

        booking.status = Booking.STATUS_QUOTED
        booking.duration_minutes = duration_minutes
        booking.estimated_price = estimated_price
        booking.save(update_fields=['status', 'duration_minutes', 'estimated_price', 'updated_at'])
        if booking.user:
            BookingNotification.objects.create(
                recipient=booking.user,
                booking=booking,
                kind=BookingNotification.KIND_STATUS_UPDATE,
                title=f'Ofertă nouă pentru programarea #{booking.pk} 💬',
                message=(
                    f"{booking.center.name} ți-a trimis un cost aproximativ de {estimated_price:.2f} RON pentru "
                    f"{booking.booking_date} la {booking.booking_time.strftime('%H:%M')} și o durată estimată de {booking.get_duration_display()}."
                ),
            )
        sms_sent = send_booking_confirmation_sms(booking)
        if sms_sent:
            messages.success(request, f'Oferta pentru programarea #{booking.pk} a fost trimisă către client și SMS-ul a fost expediat.')
        else:
            messages.success(request, f'Oferta pentru programarea #{booking.pk} a fost trimisă către client.')
    return _post_redirect(request, 'services:dashboard')


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


# ===== MECHANIC INTERFACE =====



@login_required
def parts_inventory(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')
    centers = centers.order_by('name')

    selected_center = None
    center_id = (request.GET.get('center') or request.POST.get('center_id') or '').strip()
    if center_id:
        try:
            selected_center = centers.get(pk=center_id)
        except ServiceCenter.DoesNotExist:
            selected_center = centers.first()
    else:
        selected_center = centers.first()

    if selected_center is None:
        messages.info(request, 'Adaugă mai întâi un service pentru a gestiona piesele.')
        return redirect('services:register_service')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_part':
            form = ServicePartForm(request.POST)
            if form.is_valid():
                part = form.save(commit=False)
                part.center = selected_center
                part.save()
                messages.success(request, 'Piesa a fost adăugată în stoc.')
                return redirect(f"{reverse('services:parts_inventory')}?center={selected_center.pk}")
        elif action == 'update_stock':
            part = get_object_or_404(ServicePart, pk=request.POST.get('part_id'), center__in=centers)
            try:
                stock = int(request.POST.get('stock', part.stock))
                minimum_stock = int(request.POST.get('minimum_stock', part.minimum_stock))
            except (TypeError, ValueError):
                messages.error(request, 'Valorile pentru stoc trebuie să fie numere întregi.')
            else:
                part.stock = max(stock, 0)
                part.minimum_stock = max(minimum_stock, 0)
                part.save(update_fields=['stock', 'minimum_stock', 'updated_at'])
                messages.success(request, 'Stocul piesei a fost actualizat.')
                return redirect(f"{reverse('services:parts_inventory')}?center={part.center_id}")
        elif action == 'delete_part':
            part = get_object_or_404(ServicePart, pk=request.POST.get('part_id'), center__in=centers)
            center_pk = part.center_id
            part.delete()
            messages.info(request, 'Piesa a fost ștearsă din stoc.')
            return redirect(f"{reverse('services:parts_inventory')}?center={center_pk}")
    else:
        form = ServicePartForm()

    parts = ServicePart.objects.filter(center=selected_center).order_by('name')
    return render(request, 'services/parts_inventory.html', {
        'centers': centers,
        'selected_center': selected_center,
        'parts': parts,
        'form': form,
        'low_stock_count': parts.filter(stock__lte=models.F('minimum_stock')).count(),
    })


@login_required
def service_car_history(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')

    search = (request.GET.get('q') or '').strip()
    bookings = Booking.objects.filter(
        center__in=centers,
        status=Booking.STATUS_DONE,
    ).select_related('center', 'mechanic').order_by('-booking_date', '-booking_time', '-created_at')

    if search:
        bookings = bookings.filter(
            Q(car_plate__icontains=search)
            | Q(car_vin__icontains=search)
            | Q(car_brand__icontains=search)
            | Q(car_model__icontains=search)
            | Q(client_name__icontains=search)
        )

    return render(request, 'services/car_history.html', {
        'bookings': bookings,
        'centers': centers,
        'search': search,
    })


@login_required
def mechanics_list(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')
    centers = centers.prefetch_related('garages', 'garages__category', 'categories')
    mechanics = ServiceMechanic.objects.filter(center__in=centers).select_related('center', 'garage').prefetch_related('service_categories').order_by('center', 'name')
    return render(request, 'services/mechanics_list.html', {
        'centers': centers,
        'mechanics': mechanics,
    })


@login_required
def mechanic_profile(request, pk):
    from .models import MechanicWorkLog, MechanicPhoto
    from bookings.models import Booking, BookingNotification

    mechanic = get_object_or_404(ServiceMechanic, pk=pk)
    if not (request.user.is_staff or mechanic.center.owner_id == request.user.id):
        return redirect('core:home')

    active_bookings = Booking.objects.filter(
        mechanic=mechanic, status__in=['confirmed', 'in_progress']
    ).select_related('center', 'service_item', 'garage').order_by('booking_date', 'booking_time')

    done_bookings = Booking.objects.filter(
        mechanic=mechanic, status='done'
    ).select_related('center', 'service_item').order_by('-booking_date')[:20]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_work_log':
            booking_id = request.POST.get('booking_id')
            booking = get_object_or_404(Booking, pk=booking_id, mechanic=mechanic)
            work_log, _ = MechanicWorkLog.objects.get_or_create(
                booking=booking, mechanic=mechanic
            )
            work_log.repair_description = request.POST.get('repair_description', '').strip()
            work_log.parts_used = request.POST.get('parts_used', '').strip()
            work_log.save()
            messages.success(request, 'Fișa de lucru a fost salvată.')
            return redirect('services:mechanic_profile', pk=pk)

        if action == 'upload_photos':
            booking_id = request.POST.get('booking_id')
            photo_type = request.POST.get('photo_type', 'before')
            booking = get_object_or_404(Booking, pk=booking_id, mechanic=mechanic)
            work_log, _ = MechanicWorkLog.objects.get_or_create(
                booking=booking, mechanic=mechanic
            )
            photos = request.FILES.getlist('photos')
            for photo in photos:
                MechanicPhoto.objects.create(
                    work_log=work_log,
                    photo=photo,
                    photo_type=photo_type,
                    caption=request.POST.get('caption', '').strip()
                )
            messages.success(request, f'{len(photos)} poze adăugate.')
            return redirect('services:mechanic_profile', pk=pk)

        if action == 'delete_photo':
            photo_id = request.POST.get('photo_id')
            photo = get_object_or_404(MechanicPhoto, pk=photo_id, work_log__mechanic=mechanic)
            photo.photo.delete(save=False)
            photo.delete()
            messages.info(request, 'Poza a fost ștearsă.')
            return redirect('services:mechanic_profile', pk=pk)

        if action == 'update_status':
            booking_id = request.POST.get('booking_id')
            new_status = request.POST.get('new_status')
            booking = get_object_or_404(Booking, pk=booking_id, mechanic=mechanic)
            allowed = ['in_progress', 'done']
            if new_status in allowed:
                booking.status = new_status
                booking.save(update_fields=['status', 'updated_at'])
                sms_sent = False
                if new_status == 'in_progress':
                    wl, _ = MechanicWorkLog.objects.get_or_create(booking=booking, mechanic=mechanic)
                    if not wl.started_at:
                        from django.utils import timezone
                        wl.started_at = timezone.now()
                        wl.save(update_fields=['started_at'])
                    sms_sent = send_booking_started_sms(booking)
                if new_status == 'done':
                    wl, _ = MechanicWorkLog.objects.get_or_create(booking=booking, mechanic=mechanic)
                    from django.utils import timezone
                    wl.finished_at = timezone.now()
                    wl.save(update_fields=['finished_at'])
                    sms_sent = send_booking_completed_sms(booking)
                if booking.user:
                    status_labels = {'in_progress': 'în lucru', 'done': 'finalizată'}
                    BookingNotification.objects.create(
                        recipient=booking.user,
                        booking=booking,
                        kind=BookingNotification.KIND_STATUS_UPDATE,
                        title=f"Programarea #{booking.pk} este acum {status_labels.get(new_status, new_status)}",
                        message=f"{booking.center.name}: mecanicul {mechanic.name} a actualizat statusul programării tale.",
                    )
                if sms_sent:
                    messages.success(request, 'Statusul a fost actualizat și SMS-ul a fost trimis clientului.')
                else:
                    messages.success(request, 'Statusul a fost actualizat.')
            return redirect('services:mechanic_profile', pk=pk)

    active_list = list(active_bookings)
    done_list = list(done_bookings)
    for b in active_list + done_list:
        try:
            b.work_log_obj = b.work_log
        except Exception:
            b.work_log_obj = None

    return render(request, 'services/mechanic_profile.html', {
        'mechanic': mechanic,
        'active_bookings': active_list,
        'done_bookings': done_list,
    })

@login_required
def booking_rar_pdf(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('center', 'service_item', 'user', 'garage', 'mechanic'),
        pk=pk,
    )
    if not (request.user.is_staff or booking.center.owner_id == request.user.id):
        return redirect('core:home')

    pdf_bytes = build_work_order_pdf(booking)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="fisa-interventie-{booking.pk}.pdf"'
    return response
