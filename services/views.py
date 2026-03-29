import json
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.core.cache import cache
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import login
from django.db import models
from django.db.models import Avg, Count, Min, Max, Q, Prefetch, Sum
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncMonth
from django.utils import timezone
from django.urls import reverse

from .business import (
    apply_stock_movement,
    build_vehicle_dossier,
    build_work_order_services_text,
    create_job_part_usage,
    ensure_job_card,
    rollback_job_part_usage,
    sync_booking_from_job_card,
    transition_booking_status,
    transition_job_card_status,
    validate_job_card_status_for_booking,
)
from .models import (
    JobCard,
    JobOperation,
    JobPartUsage,
    JobRecommendation,
    ServiceAvailabilityBlock,
    ServiceCategory,
    ServiceCenter,
    ServiceGarage,
    ServiceImage,
    ServiceItem,
    ServiceMechanic,
    Review,
    Favorite,
    ReviewImage,
    ServicePart,
    StockMovement,
)
from .forms import (
    AvailabilityBlockForm,
    JobCardForm,
    JobOperationForm,
    JobPartUsageForm,
    JobRecommendationForm,
    ServiceCenterRegisterForm,
    ServiceCenterPublicRegisterForm,
    ServiceGarageForm,
    ServiceGalleryImageForm,
    ServiceMechanicForm,
    ServiceOwnerBookingForm,
    ReviewForm,
    ServicePartForm,
    StockMovementForm,
    ReportFilterForm,
)
from bookings.activity import log_booking_activity
from bookings.files import prepare_uploaded_file, sanitize_uploaded_filename
from bookings.models import Booking, BookingNotification, BookingAttachment, BookingChecklistItem
from invoices.models import Invoice
from core.pdf_utils import build_work_order_pdf
from .reporting import build_dashboard_metrics, build_report, export_report_csv
from accounts.views import _record_legal_acceptance
from core.services.sms_service import (
    send_booking_completed_sms,
    send_booking_confirmation_sms,
    send_booking_started_sms,
)
from core.services.email_service import (
    send_booking_completed_email,
    send_booking_quote_email,
    send_booking_started_email,
)
from core.upload_validators import validate_booking_media_file, validate_image_file


def _post_redirect(request, fallback):
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect(fallback)


def _paginate_queryset(request, queryset, per_page=20, page_param='page'):
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get(page_param))
    return page_obj


def _calendar_status_config():
    return {
        Booking.STATUS_PENDING: {'label': 'In asteptare', 'color': '#facc15'},
        Booking.STATUS_QUOTED: {'label': 'Ofertat', 'color': '#94a3b8'},
        Booking.STATUS_CONFIRMED: {'label': 'Confirmat', 'color': '#22c55e'},
        Booking.STATUS_IN_PROGRESS: {'label': 'In progres', 'color': '#f97316'},
        Booking.STATUS_WAITING_PARTS: {'label': 'Asteapta piese', 'color': '#ef4444'},
        Booking.STATUS_DONE: {'label': 'Finalizat', 'color': '#6366f1'},
        Booking.STATUS_CANCELLED: {'label': 'Anulat', 'color': '#ef4444'},
    }


def _booking_calendar_attention(booking):
    reasons = []
    if booking.needs_attention():
        if booking.status in {Booking.STATUS_CONFIRMED, Booking.STATUS_IN_PROGRESS, Booking.STATUS_WAITING_PARTS} and not booking.garage_id:
            reasons.append('Lipseste garajul')
        if booking.status in {Booking.STATUS_IN_PROGRESS, Booking.STATUS_WAITING_PARTS} and not booking.mechanic_id:
            reasons.append('Lipseste mecanicul')
        if booking.has_operational_tag(Booking.TAG_BLOCKED):
            reasons.append('Marcat ca blocat')
        if booking.status == Booking.STATUS_WAITING_PARTS or booking.has_operational_tag(Booking.TAG_WAITING_PART):
            reasons.append('Asteapta piesa')
    return reasons


def _capacity_label(booked_minutes, available_minutes):
    if available_minutes <= 0:
        return 'Suprarezervat'
    load_ratio = booked_minutes / available_minutes
    if load_ratio >= 1:
        return 'Suprarezervat'
    if load_ratio >= 0.75:
        return 'Aproape plin'
    return 'Liber'


def _capacity_badge(load_label):
    return {
        'Liber': 'success',
        'Aproape plin': 'warning text-dark',
        'Suprarezervat': 'danger',
    }.get(load_label, 'secondary')


def _resource_capacity_snapshot(centers, day_bookings, target_date):
    mechanics_capacity = []
    for mechanic in ServiceMechanic.objects.filter(center__in=centers).select_related('center', 'garage').order_by('center__name', 'name'):
        mechanic_bookings = [booking for booking in day_bookings if booking.mechanic_id == mechanic.pk]
        booked_minutes = sum(booking.effective_duration_minutes() for booking in mechanic_bookings)
        available_minutes = 8 * 60
        load_label = _capacity_label(booked_minutes, available_minutes)
        mechanics_capacity.append({
            'mechanic': mechanic,
            'todays_count': len(mechanic_bookings),
            'booked_minutes': booked_minutes,
            'available_minutes': available_minutes,
            'load_percent': min(round((booked_minutes / available_minutes) * 100), 100) if available_minutes else 100,
            'load_label': load_label,
            'load_badge': _capacity_badge(load_label),
        })

    garages_capacity = []
    for garage in ServiceGarage.objects.filter(center__in=centers).select_related('center').order_by('center__name', 'name'):
        garage_bookings = [booking for booking in day_bookings if booking.garage_id == garage.pk]
        available_minutes = max(
            int((datetime.combine(target_date, garage.close_time) - datetime.combine(target_date, garage.open_time)).total_seconds() // 60),
            0,
        )
        booked_minutes = sum(booking.effective_duration_minutes() for booking in garage_bookings)
        load_label = _capacity_label(booked_minutes, available_minutes)
        garages_capacity.append({
            'garage': garage,
            'todays_count': len(garage_bookings),
            'booked_minutes': booked_minutes,
            'available_minutes': available_minutes,
            'load_percent': min(round((booked_minutes / available_minutes) * 100), 100) if available_minutes else 100,
            'load_label': load_label,
            'load_badge': _capacity_badge(load_label),
        })

    return mechanics_capacity, garages_capacity


def _parts_dashboard_stats(centers):
    parts_qs = ServicePart.objects.filter(center__in=centers)
    return {
        'total_parts': parts_qs.count(),
        'low_stock_count': parts_qs.filter(stock__lte=models.F('minimum_stock')).count(),
        'out_of_stock_count': parts_qs.filter(stock=0).count(),
        'estimated_stock_value': parts_qs.aggregate(
            total=Sum(
                models.F('stock') * models.F('price'),
                output_field=models.DecimalField(max_digits=14, decimal_places=2),
            )
        )['total'] or Decimal('0.00'),
        'low_stock_parts': list(
            parts_qs.filter(stock__lte=models.F('minimum_stock'))
            .select_related('center')
            .order_by('stock', 'name')[:6]
        ),
    }


def _build_dashboard_analytics(bookings_qs, centers, user_id):
    booking_last_update = bookings_qs.aggregate(last=Max('updated_at'))['last']
    invoice_last_update = Invoice.objects.filter(center__in=centers).aggregate(last=Max('updated_at'))['last']
    booking_version = int(booking_last_update.timestamp()) if booking_last_update else 0
    invoice_version = int(invoice_last_update.timestamp()) if invoice_last_update else 0
    analytics_cache_key = f"service_dashboard_analytics:{user_id}:{booking_version}:{invoice_version}"
    analytics = cache.get(analytics_cache_key)
    if analytics is not None:
        return analytics

    booking_summary = bookings_qs.aggregate(
        total_count=Count('id'),
        pending_count=Count('id', filter=Q(status=Booking.STATUS_PENDING)),
        quoted_count=Count('id', filter=Q(status=Booking.STATUS_QUOTED)),
        confirmed_count=Count('id', filter=Q(status=Booking.STATUS_CONFIRMED)),
        in_progress_count=Count('id', filter=Q(status=Booking.STATUS_IN_PROGRESS)),
        done_count=Count('id', filter=Q(status=Booking.STATUS_DONE)),
        cancelled_count=Count('id', filter=Q(status=Booking.STATUS_CANCELLED)),
        estimated_revenue=Sum('estimated_price', filter=Q(status__in=[
            Booking.STATUS_QUOTED,
            Booking.STATUS_CONFIRMED,
            Booking.STATUS_IN_PROGRESS,
            Booking.STATUS_DONE,
        ])),
    )

    invoices_total = Invoice.objects.filter(
        center__in=centers,
        status=Invoice.STATUS_FINAL,
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    top_services = list(
        bookings_qs.exclude(service_item__isnull=True).values('service_item__name')
        .annotate(total=Count('id'))
        .order_by('-total', 'service_item__name')[:5]
    )
    top_mechanics = list(
        bookings_qs.filter(status=Booking.STATUS_DONE, mechanic__isnull=False)
        .values('mechanic__name')
        .annotate(total=Count('id'))
        .order_by('-total', 'mechanic__name')[:5]
    )
    recurring_clients = bookings_qs.exclude(client_email='').values('client_email').annotate(
        total=Count('id')
    ).filter(total__gte=2).count()
    review_stats = ServiceCenter.objects.filter(pk__in=centers.values('pk')).aggregate(
        avg_rating=Avg('review__rating', filter=Q(review__is_approved=True)),
        total_reviews=Count('review', filter=Q(review__is_approved=True)),
    )

    month_points = list(
        bookings_qs.annotate(month=TruncMonth('booking_date'))
        .values('month')
        .annotate(
            total=Count('id'),
            confirmed=Count('id', filter=Q(status=Booking.STATUS_CONFIRMED)),
            done=Count('id', filter=Q(status=Booking.STATUS_DONE)),
            cancelled=Count('id', filter=Q(status=Booking.STATUS_CANCELLED)),
            revenue=Sum('estimated_price', filter=Q(status__in=[
                Booking.STATUS_QUOTED,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_IN_PROGRESS,
                Booking.STATUS_DONE,
            ])),
        )
        .order_by('-month')[:6]
    )
    month_points.reverse()
    monthly_trend = [
        {
            'label': item['month'].strftime('%b %Y') if item['month'] else '',
            'total': item['total'],
            'confirmed': item['confirmed'],
            'done': item['done'],
            'cancelled': item['cancelled'],
            'revenue': float(item['revenue'] or 0),
        }
        for item in month_points
    ]

    today = timezone.localdate()
    today_count = bookings_qs.filter(booking_date=today).count()
    busiest_hours = list(
        bookings_qs.annotate(hour=ExtractHour('booking_time'))
        .values('hour')
        .annotate(total=Count('id'))
        .order_by('-total', 'hour')[:5]
    )
    weekday_labels = {
        1: 'Duminica', 2: 'Luni', 3: 'Marti', 4: 'Miercuri', 5: 'Joi', 6: 'Vineri', 7: 'Sambata'
    }
    busiest_days = list(
        bookings_qs.annotate(weekday=ExtractWeekDay('booking_date'))
        .values('weekday')
        .annotate(total=Count('id'))
        .order_by('-total', 'weekday')[:5]
    )

    total_bookings = booking_summary['total_count'] or 0
    quoted_count = booking_summary['quoted_count'] or 0
    accepted_count = (booking_summary['confirmed_count'] or 0) + (booking_summary['in_progress_count'] or 0) + (booking_summary['done_count'] or 0)
    completed_count = booking_summary['done_count'] or 0

    analytics = {
        'total_bookings': total_bookings,
        'pending_count': booking_summary['pending_count'] or 0,
        'quoted_count': quoted_count,
        'accepted_count': accepted_count,
        'completed_count': completed_count,
        'in_progress_count': booking_summary['in_progress_count'] or 0,
        'cancelled_count': booking_summary['cancelled_count'] or 0,
        'quote_rate': round((quoted_count / total_bookings) * 100, 1) if total_bookings else 0,
        'acceptance_rate': round((accepted_count / quoted_count) * 100, 1) if quoted_count else 0,
        'completion_rate': round((completed_count / accepted_count) * 100, 1) if accepted_count else 0,
        'estimated_revenue': booking_summary['estimated_revenue'] or Decimal('0.00'),
        'invoiced_revenue': invoices_total,
        'top_services': top_services,
        'top_mechanics': top_mechanics,
        'recurring_clients': recurring_clients,
        'avg_rating': round(review_stats['avg_rating'] or 0, 1),
        'total_reviews': review_stats['total_reviews'] or 0,
        'monthly_trend': monthly_trend,
        'today_count': today_count,
        'busiest_hours': [
            {'label': f"{item['hour']:02d}:00" if item['hour'] is not None else 'Fara ora', 'total': item['total']}
            for item in busiest_hours
        ],
        'busiest_days': [
            {'label': weekday_labels.get(item['weekday'], str(item['weekday'])), 'total': item['total']}
            for item in busiest_days
        ],
    }
    cache.set(analytics_cache_key, analytics, 120)
    return analytics


def category_list(request):
    categories = ServiceCategory.objects.all().order_by('order')
    for cat in categories:
        cat.center_count_display = ServiceCenter.objects.filter(
            Q(category=cat) | Q(categories=cat),
            is_active=True
        ).distinct().count()
    return render(request, 'services/categories.html', {'categories': categories})


def service_list(request):
    from django.db.models import Subquery, OuterRef, FloatField, IntegerField, Case, When, Value, F
    from django.db.models.functions import Coalesce
    today = timezone.localdate()

    min_price_sq = Subquery(
        ServiceItem.objects.filter(center=OuterRef('pk'))
        .order_by('price_from').values('price_from')[:1]
    )

    qs = ServiceCenter.objects.filter(is_active=True).annotate(
        avg_rating=Avg('review__rating', filter=Q(review__is_approved=True)),
        review_count=Count('review', filter=Q(review__is_approved=True), distinct=True),
        min_price=min_price_sq,
        garage_count=Count('garages', distinct=True),
        active_mechanics=Count('mechanics', filter=Q(mechanics__is_active=True), distinct=True),
        future_bookings=Count(
            'bookings',
            filter=Q(
                bookings__booking_date__gte=today,
                bookings__status__in=[
                    Booking.STATUS_QUOTED,
                    Booking.STATUS_CONFIRMED,
                    Booking.STATUS_IN_PROGRESS,
                ],
            ),
            distinct=True,
        ),
        profile_completeness=(
            Case(When(description__gt='', then=Value(1)), default=Value(0), output_field=IntegerField()) +
            Case(When(email__gt='', then=Value(1)), default=Value(0), output_field=IntegerField()) +
            Case(When(phone__gt='', then=Value(1)), default=Value(0), output_field=IntegerField()) +
            Case(When(website__gt='', then=Value(1)), default=Value(0), output_field=IntegerField()) +
            Case(When(card_image__isnull=False, then=Value(1)), default=Value(0), output_field=IntegerField())
        ),
    ).prefetch_related('categories')
    qs = qs.annotate(
        ranking_score=(
            Coalesce(F('avg_rating'), Value(0.0), output_field=FloatField()) * Value(2.5) +
            Coalesce(F('review_count'), Value(0), output_field=FloatField()) * Value(0.35) +
            Coalesce(F('profile_completeness'), Value(0), output_field=FloatField()) * Value(0.7) +
            Coalesce(F('garage_count'), Value(0), output_field=FloatField()) * Value(0.5) +
            Coalesce(F('active_mechanics'), Value(0), output_field=FloatField()) * Value(0.45) +
            Case(
                When(future_bookings__lte=2, then=Value(1.1)),
                When(future_bookings__lte=5, then=Value(0.5)),
                default=Value(0.0),
                output_field=FloatField(),
            ) +
            Case(When(is_featured=True, then=Value(1.2)), default=Value(0.0), output_field=FloatField())
        )
    )

    category_slug = request.GET.get('category', '').strip()
    city = request.GET.get('city', '').strip()
    min_rating = request.GET.get('min_rating', '').strip()
    price_min = request.GET.get('price_min', '').strip()
    price_max = request.GET.get('price_max', '').strip()
    sort_by = request.GET.get('sort', 'recommended')
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

    sort_options = {
        'recommended': F('ranking_score').desc(nulls_last=True),
        'rating': F('avg_rating').desc(nulls_last=True),
        'price_asc': F('min_price').asc(nulls_last=True),
        'price_desc': F('min_price').desc(nulls_last=True),
        'reviews': F('review_count').desc(nulls_last=True),
        'name': F('name').asc(),
        # 'distance' e tratat client-side cu JS/GPS - server face fallback la rating
        'distance': F('ranking_score').desc(nulls_last=True),
    }
    qs = qs.order_by(sort_options.get(sort_by, F('ranking_score').desc(nulls_last=True)))

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
    dashboard = build_dashboard_metrics(centers)
    service_name = centers.first().name if centers.count() == 1 else 'Service-urile tale'

    return render(request, 'services/service_dashboard.html', {
        'centers': centers,
        'service_name': service_name,
        'dashboard': dashboard,
        'current_date': timezone.localdate(),
    })


@login_required
def service_reports(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')

    form = ReportFilterForm(request.GET or None)
    if form.is_valid():
        cleaned = form.cleaned_data
    else:
        cleaned = {'report_type': 'performance', 'preset_period': 'this_month'}
        form = ReportFilterForm(initial=cleaned)

    report_payload = build_report(centers, cleaned)
    return render(request, 'services/service_reports.html', {
        'centers': centers,
        'form': form,
        'report': report_payload,
        'report_chart_json': json.dumps(report_payload.get('chart', {})),
    })


@login_required
def export_report_csv_view(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')

    form = ReportFilterForm(request.GET or None)
    cleaned = form.cleaned_data if form.is_valid() else {'report_type': 'performance', 'preset_period': 'this_month'}
    report_payload = build_report(centers, cleaned)
    period = report_payload['period']
    filename_period = f"{period.start.isoformat()}_{period.end.isoformat()}" if period.start != period.end else period.start.isoformat()
    filename = f"raport_{report_payload['report_type']}_{filename_period}.csv"
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('﻿')
    return export_report_csv(response, report_payload)


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
def service_calendar(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')

    centers = centers.prefetch_related('garages', 'categories')
    selected_center = centers.first()
    center_id = (request.POST.get('center_id') or request.GET.get('center') or '').strip()
    if center_id.isdigit():
        selected_center = centers.filter(pk=int(center_id)).first() or selected_center

    if request.method == 'POST' and selected_center:
        availability_form = AvailabilityBlockForm(request.POST, center=selected_center)
        if availability_form.is_valid():
            block = availability_form.save(commit=False)
            block.center = selected_center
            block.created_by = request.user
            block.save()
            messages.success(request, 'Intervalul indisponibil a fost salvat in calendar.')
            return redirect(f"{reverse('services:calendar')}?center={selected_center.pk}")
    else:
        availability_form = AvailabilityBlockForm(center=selected_center)

    today = timezone.localdate()
    today_bookings = Booking.objects.filter(center__in=centers, booking_date=today).count()
    garages = ServiceGarage.objects.filter(center__in=centers).order_by('center__name', 'name')
    mechanics = ServiceMechanic.objects.filter(center__in=centers).order_by('center__name', 'name')
    service_items = ServiceItem.objects.filter(center__in=centers).order_by('center__name', 'name')
    recent_blocks = ServiceAvailabilityBlock.objects.filter(center__in=centers).select_related(
        'center', 'garage', 'mechanic'
    ).order_by('-created_at', '-starts_at', '-pk')[:8]

    return render(request, 'services/service_calendar.html', {
        'centers': centers,
        'selected_center': selected_center,
        'today_bookings': today_bookings,
        'calendar_statuses': _calendar_status_config(),
        'calendar_garages': garages,
        'calendar_mechanics': mechanics,
        'calendar_services': service_items,
        'availability_form': availability_form,
        'recent_blocks': recent_blocks,
    })


@login_required
def service_calendar_events(request):
    centers = _require_service_owner(request)
    if centers is None:
        return JsonResponse({'ok': False, 'detail': 'service_required'}, status=403)

    start_raw = (request.GET.get('start') or '').strip()
    end_raw = (request.GET.get('end') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()
    garage_filter = (request.GET.get('garage') or '').strip()
    mechanic_filter = (request.GET.get('mechanic') or '').strip()
    service_filter = (request.GET.get('service_item') or '').strip()

    bookings = Booking.objects.filter(center__in=centers).select_related(
        'center', 'garage', 'mechanic', 'service_item'
    )

    if start_raw:
        try:
            start_date = datetime.fromisoformat(start_raw.replace('Z', '+00:00')).date()
            bookings = bookings.filter(booking_date__gte=start_date)
        except ValueError:
            pass
    if end_raw:
        try:
            end_date = datetime.fromisoformat(end_raw.replace('Z', '+00:00')).date()
            bookings = bookings.filter(booking_date__lt=end_date)
        except ValueError:
            pass

    if status_filter:
        allowed_statuses = {choice[0] for choice in Booking.STATUS_CHOICES}
        selected_statuses = [item for item in status_filter.split(',') if item in allowed_statuses]
        if selected_statuses:
            bookings = bookings.filter(status__in=selected_statuses)
    if garage_filter.isdigit():
        bookings = bookings.filter(garage_id=int(garage_filter))
    if mechanic_filter.isdigit():
        bookings = bookings.filter(mechanic_id=int(mechanic_filter))
    if service_filter.isdigit():
        bookings = bookings.filter(service_item_id=int(service_filter))

    status_config = _calendar_status_config()
    events = []
    for booking in bookings.order_by('booking_date', 'booking_time', 'pk'):
        start_dt = booking.get_start_datetime()
        end_dt = booking.get_end_datetime()
        config = status_config.get(booking.status, {'label': booking.get_status_display(), 'color': '#94a3b8'})
        attention_reasons = _booking_calendar_attention(booking)
        events.append({
            'id': booking.pk,
            'title': f"#{booking.pk} {booking.client_name}",
            'start': start_dt.isoformat() if start_dt else None,
            'end': end_dt.isoformat() if end_dt else None,
            'url': reverse('services:booking_detail', args=[booking.pk]),
            'backgroundColor': config['color'],
            'borderColor': config['color'],
            'textColor': '#0f172a' if booking.status == Booking.STATUS_PENDING else '#ffffff',
            'extendedProps': {
                'status': booking.status,
                'status_label': booking.get_status_display(),
                'center': booking.center.name,
                'garage': booking.garage.name if booking.garage_id else 'Fara garaj',
                'mechanic': booking.mechanic.name if booking.mechanic_id else 'Nealocat',
                'car': f"{booking.car_brand} {booking.car_model} ({booking.car_plate})",
                'service': booking.service_item.name if booking.service_item_id else 'Fara serviciu selectat',
                'problem_description': booking.problem_description,
                'duration': booking.get_duration_display(),
                'estimated_price': f"{booking.estimated_price:.2f} RON" if booking.estimated_price is not None else '',
                'booking_date': booking.booking_date.strftime('%d.%m.%Y'),
                'booking_time': booking.booking_time.strftime('%H:%M'),
                'needs_attention': bool(attention_reasons),
                'attention_reasons': attention_reasons,
            },
        })

    blocks = ServiceAvailabilityBlock.objects.filter(center__in=centers).select_related(
        'center', 'garage', 'mechanic'
    )
    if start_raw:
        try:
            start_date = datetime.fromisoformat(start_raw.replace('Z', '+00:00'))
            blocks = blocks.filter(ends_at__gte=start_date)
        except ValueError:
            pass
    if end_raw:
        try:
            end_date = datetime.fromisoformat(end_raw.replace('Z', '+00:00'))
            blocks = blocks.filter(starts_at__lte=end_date)
        except ValueError:
            pass
    if garage_filter.isdigit():
        blocks = blocks.filter(garage_id=int(garage_filter))
    if mechanic_filter.isdigit():
        blocks = blocks.filter(mechanic_id=int(mechanic_filter))

    for block in blocks.order_by('starts_at', 'pk'):
        title_target = block.garage.name if block.garage_id else block.mechanic.name
        events.append({
            'id': f'block-{block.pk}',
            'title': f'{block.title} · {title_target}',
            'start': timezone.localtime(block.starts_at).isoformat() if timezone.is_aware(block.starts_at) else block.starts_at.isoformat(),
            'end': timezone.localtime(block.ends_at).isoformat() if timezone.is_aware(block.ends_at) else block.ends_at.isoformat(),
            'display': 'background',
            'backgroundColor': '#7f1d1d',
            'borderColor': '#991b1b',
            'textColor': '#ffffff',
            'extendedProps': {
                'status': 'availability_block',
                'status_label': dict(ServiceAvailabilityBlock.BLOCK_TYPE_CHOICES).get(block.block_type, 'Indisponibil'),
                'center': block.center.name,
                'garage': block.garage.name if block.garage_id else 'Nespecificat',
                'mechanic': block.mechanic.name if block.mechanic_id else 'Nespecificat',
                'car': 'Interval indisponibil',
                'service': block.title,
                'problem_description': block.notes,
                'duration': '',
                'estimated_price': '',
                'booking_date': timezone.localtime(block.starts_at).strftime('%d.%m.%Y') if timezone.is_aware(block.starts_at) else block.starts_at.strftime('%d.%m.%Y'),
                'booking_time': timezone.localtime(block.starts_at).strftime('%H:%M') if timezone.is_aware(block.starts_at) else block.starts_at.strftime('%H:%M'),
                'needs_attention': False,
                'attention_reasons': [],
            },
        })

    return JsonResponse(events, safe=False)


@login_required
def service_calendar_update_booking(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('center', 'garage', 'mechanic', 'service_item'),
        pk=pk,
    )
    if not (request.user.is_staff or booking.center.owner_id == request.user.id):
        return JsonResponse({'ok': False, 'detail': 'forbidden'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'detail': 'method_not_allowed'}, status=405)
    if booking.status in {Booking.STATUS_DONE, Booking.STATUS_CANCELLED}:
        return JsonResponse({'ok': False, 'detail': 'locked', 'message': 'Programarile finalizate sau anulate nu mai pot fi mutate din calendar.'}, status=400)

    payload = request.POST or request.GET
    start_raw = (payload.get('start') or '').strip()
    end_raw = (payload.get('end') or '').strip()
    if not start_raw or not end_raw:
        return JsonResponse({'ok': False, 'message': 'Lipsesc data de inceput sau data de final.'}, status=400)

    try:
        new_start = datetime.fromisoformat(start_raw.replace('Z', '+00:00'))
        new_end = datetime.fromisoformat(end_raw.replace('Z', '+00:00'))
    except ValueError:
        return JsonResponse({'ok': False, 'message': 'Intervalul trimis nu este valid.'}, status=400)

    if timezone.is_aware(new_start):
        new_start = timezone.localtime(new_start).replace(tzinfo=None)
    if timezone.is_aware(new_end):
        new_end = timezone.localtime(new_end).replace(tzinfo=None)

    duration_minutes = int((new_end - new_start).total_seconds() // 60)
    if duration_minutes < 30:
        return JsonResponse({'ok': False, 'message': 'Durata minima este de 30 minute.'}, status=400)

    old_snapshot = {
        'date': booking.booking_date.isoformat(),
        'time': booking.booking_time.strftime('%H:%M'),
        'duration': booking.effective_duration_minutes(),
    }
    booking.booking_date = new_start.date()
    booking.booking_time = new_start.time().replace(second=0, microsecond=0)
    booking.duration_minutes = duration_minutes

    try:
        booking.full_clean()
        booking.save(update_fields=['booking_date', 'booking_time', 'duration_minutes', 'updated_at'])
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'message': '; '.join(exc.messages)}, status=400)

    log_booking_activity(
        booking,
        'schedule_changed',
        f'Programarea a fost mutata in calendar pe {booking.booking_date:%d.%m.%Y} la {booking.booking_time:%H:%M}.',
        actor=request.user,
        metadata={
            'old': old_snapshot,
            'new': {
                'date': booking.booking_date.isoformat(),
                'time': booking.booking_time.strftime('%H:%M'),
                'duration': booking.duration_minutes,
            },
        },
    )
    return JsonResponse({
        'ok': True,
        'message': 'Programarea a fost actualizata.',
        'duration_display': booking.get_duration_display(),
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
                try:
                    validate_image_file(request.FILES['photo'], label='Fotografia mecanicului')
                except ValidationError as exc:
                    messages.error(request, exc.message)
                    return _post_redirect(request, 'services:dashboard')
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
            try:
                validate_image_file(request.FILES['photo'], label='Fotografia mecanicului')
            except ValidationError as exc:
                messages.error(request, exc.message)
                return redirect('services:mechanic_profile', pk=pk)
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
        Booking.objects.select_related('center', 'service_item', 'user', 'garage', 'mechanic').prefetch_related(
            'attachments', 'activity_logs__actor', 'checklist_items'
        ),
        pk=pk,
    )
    if not (request.user.is_staff or booking.center.owner_id == request.user.id):
        return redirect('core:home')

    mechanics = booking.center.mechanics.order_by('name')
    job_card, _ = ensure_job_card(booking, actor=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_work_order_info':
            previous_used_services = booking.used_services
            previous_description = booking.additional_description
            booking.used_services = (request.POST.get('used_services') or '').strip()
            booking.additional_description = (request.POST.get('additional_description') or '').strip()
            booking.save(update_fields=['used_services', 'additional_description', 'updated_at'])
            if booking.used_services != previous_used_services or booking.additional_description != previous_description:
                log_booking_activity(booking, 'note_updated', 'Fisa de lucru a fost actualizata.', actor=request.user)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({'ok': True, 'msg': 'Fișa a fost salvată.'})
            messages.success(request, 'Detaliile suplimentare pentru fișa de comandă au fost salvate.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'save_internal_notes':
            previous_notes = booking.notes
            booking.notes = (request.POST.get('notes') or '').strip()
            booking.save(update_fields=['notes', 'updated_at'])
            if booking.notes != previous_notes:
                log_booking_activity(booking, 'note_updated', 'Nota interna a fost actualizata.', actor=request.user)
            messages.success(request, 'Nota interna a fost salvata.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'save_job_card':
            form = JobCardForm(request.POST, instance=job_card, center=booking.center)
            if form.is_valid():
                previous_status = job_card.status
                previous_mechanic_id = job_card.mechanic_id
                candidate = form.save(commit=False)
                try:
                    validate_job_card_status_for_booking(booking, candidate.status)
                except ValidationError as exc:
                    form.add_error('status', exc.message)
                else:
                    job_card = candidate
                    job_card.booking = booking
                    job_card.center = booking.center
                    job_card.updated_by = request.user
                    if not job_card.created_by_id:
                        job_card.created_by = request.user
                    job_card.save()
                    if previous_status != job_card.status:
                        log_booking_activity(
                            booking,
                            'status_changed',
                            f'Fisa lucrarii a fost actualizata in statusul {job_card.get_status_display()}.',
                            actor=request.user,
                            metadata={'old': previous_status, 'new': job_card.status, 'scope': 'job_card'},
                        )
                    if previous_mechanic_id != job_card.mechanic_id:
                        booking.mechanic = job_card.mechanic
                        booking.save(update_fields=['mechanic', 'updated_at'])
                    sync_booking_from_job_card(job_card, actor=request.user)
                    messages.success(request, 'Fisa lucrarii a fost actualizata.')
                    return redirect('services:booking_detail', pk=booking.pk)

            messages.error(request, '; '.join(form.errors.get_json_data(escape_html=False).keys()) or 'Formularul fisei lucrarii contine erori.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'add_operation':
            form = JobOperationForm(request.POST)
            if form.is_valid():
                operation = form.save(commit=False)
                operation.job_card = job_card
                operation.position = job_card.operations.count() + 1
                operation.save()
                log_booking_activity(booking, 'note_updated', f'A fost adaugata operatiunea: {operation.title}.', actor=request.user)
                messages.success(request, 'Operatiunea a fost adaugata in fisa lucrarii.')
            else:
                messages.error(request, 'Operatiunea nu a putut fi salvata.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'delete_operation':
            operation = get_object_or_404(JobOperation, pk=request.POST.get('operation_id'), job_card=job_card)
            title = operation.title
            operation.delete()
            log_booking_activity(booking, 'note_updated', f'Operatiunea "{title}" a fost eliminata din fisa lucrarii.', actor=request.user)
            messages.info(request, 'Operatiunea a fost stearsa.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'add_recommendation':
            form = JobRecommendationForm(request.POST)
            if form.is_valid():
                recommendation = form.save(commit=False)
                recommendation.job_card = job_card
                recommendation.save()
                log_booking_activity(booking, 'note_updated', f'A fost adaugata recomandarea: {recommendation.title}.', actor=request.user)
                messages.success(request, 'Recomandarea a fost salvata.')
            else:
                messages.error(request, 'Recomandarea nu a putut fi salvata.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'toggle_recommendation':
            recommendation = get_object_or_404(JobRecommendation, pk=request.POST.get('recommendation_id'), job_card=job_card)
            recommendation.is_resolved = not recommendation.is_resolved
            recommendation.resolved_at = timezone.now() if recommendation.is_resolved else None
            recommendation.save(update_fields=['is_resolved', 'resolved_at'])
            log_booking_activity(
                booking,
                'note_updated',
                f'Recomandarea "{recommendation.title}" a fost {"marcata ca rezolvata" if recommendation.is_resolved else "redeschisa"}.',
                actor=request.user,
            )
            messages.info(request, 'Starea recomandarii a fost actualizata.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'add_job_part':
            form = JobPartUsageForm(request.POST, center=booking.center)
            if form.is_valid():
                try:
                    usage = create_job_part_usage(
                        job_card,
                        part=form.cleaned_data['part'],
                        quantity=form.cleaned_data['quantity'],
                        status=form.cleaned_data['status'],
                        actor=request.user,
                        note=form.cleaned_data['note'],
                    )
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                else:
                    if usage.status == JobPartUsage.STATUS_RESERVED and job_card.status not in {JobCard.STATUS_WAITING_PARTS, JobCard.STATUS_IN_PROGRESS}:
                        transition_job_card_status(job_card, JobCard.STATUS_APPROVED, actor=request.user, sync_booking=True)
                    log_booking_activity(
                        booking,
                        'note_updated',
                        f'A fost adaugata piesa "{usage.description}" x{usage.quantity} in fisa lucrarii.',
                        actor=request.user,
                    )
                    messages.success(request, 'Piesa a fost inregistrata si stocul a fost actualizat.')
            else:
                messages.error(request, 'Piesa nu a putut fi adaugata.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'delete_job_part':
            usage = get_object_or_404(JobPartUsage, pk=request.POST.get('usage_id'), job_card=job_card)
            rollback_job_part_usage(usage, actor=request.user)
            log_booking_activity(booking, 'note_updated', 'O piesa a fost scoasa din fisa lucrarii si stocul a fost refacut.', actor=request.user)
            messages.info(request, 'Piesa a fost eliminata din fisa lucrarii.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'update_tags':
            selected_tags = [tag for tag in request.POST.getlist('operational_tags') if tag in dict(Booking.TAG_CHOICES)]
            previous_tags = list(booking.operational_tags or [])
            booking.operational_tags = selected_tags
            try:
                booking.full_clean()
                booking.save(update_fields=['operational_tags', 'updated_at'])
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
                return redirect('services:booking_detail', pk=booking.pk)
            if booking.operational_tags != previous_tags:
                log_booking_activity(
                    booking,
                    'tags_updated',
                    'Tag-urile operationale au fost actualizate.',
                    actor=request.user,
                    metadata={'old': previous_tags, 'new': booking.operational_tags},
                )
            messages.success(request, 'Tag-urile operationale au fost actualizate.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'add_checklist_item':
            label = (request.POST.get('label') or '').strip()
            if not label:
                messages.error(request, 'Introdu un pas valid pentru checklist.')
                return redirect('services:booking_detail', pk=booking.pk)
            item = BookingChecklistItem.objects.create(booking=booking, label=label, created_by=request.user)
            log_booking_activity(booking, 'checklist_updated', f'A fost adaugat in checklist: {item.label}.', actor=request.user)
            messages.success(request, 'Checklist-ul a fost actualizat.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'toggle_checklist_item':
            item = get_object_or_404(BookingChecklistItem, pk=request.POST.get('item_id'), booking=booking)
            item.is_done = not item.is_done
            item.completed_at = timezone.now() if item.is_done else None
            item.save(update_fields=['is_done', 'completed_at'])
            log_booking_activity(
                booking,
                'checklist_updated',
                f'Checklist: {item.label} a fost {"bifat" if item.is_done else "redeschis"}.',
                actor=request.user,
            )
            messages.info(request, 'Checklist-ul a fost actualizat.')
            return redirect('services:booking_detail', pk=booking.pk)

        if action == 'assign_mechanic':
            mechanic_id = (request.POST.get('mechanic') or '').strip()
            old_mechanic = booking.mechanic.name if booking.mechanic_id else ''
            mechanic = None
            if mechanic_id:
                mechanic = get_object_or_404(ServiceMechanic, pk=mechanic_id, center=booking.center)
            booking.mechanic = mechanic
            try:
                booking.full_clean()
                booking.save(update_fields=['mechanic', 'updated_at'])
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
                return redirect('services:booking_detail', pk=booking.pk)
            if job_card.mechanic_id != booking.mechanic_id:
                job_card.mechanic = booking.mechanic
                job_card.updated_by = request.user
                job_card.save(update_fields=['mechanic', 'updated_by', 'updated_at'])
            log_booking_activity(
                booking,
                'mechanic_changed',
                f'Mecanicul a fost {"alocat" if mechanic else "eliminat"} pentru programare.',
                actor=request.user,
                metadata={'old': old_mechanic, 'new': mechanic.name if mechanic else ''},
            )
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
                uploaded = prepare_uploaded_file(uploaded)
                try:
                    validate_booking_media_file(uploaded)
                except Exception:
                    continue
                content_type = getattr(uploaded, 'content_type', '') or ''
                media_kind = 'video' if content_type.startswith('video/') else 'image'
                BookingAttachment.objects.create(booking=booking, file=uploaded, media_kind=media_kind)
                log_booking_activity(
                    booking,
                    'attachment_added',
                    f'A fost adaugat un fisier: {sanitize_uploaded_filename(uploaded.name)}.',
                    actor=request.user,
                    metadata={'filename': uploaded.name, 'media_kind': media_kind},
                )
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
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'ok': False, 'msg': 'Status invalid.'})
                messages.error(request, 'Statusul selectat nu este valid.')
                return redirect('services:booking_detail', pk=booking.pk)
            try:
                old_status, changed, job_card = transition_booking_status(
                    booking,
                    new_status,
                    actor=request.user,
                    sync_job_card=True,
                    create_job_card=True,
                )
            except ValidationError as exc:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'ok': False, 'msg': '; '.join(exc.messages)})
                messages.error(request, '; '.join(exc.messages))
                return redirect('services:booking_detail', pk=booking.pk)
            if not changed:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'ok': True, 'msg': 'Statusul era deja setat.', 'status_display': booking.get_status_display(), 'status_badge': booking.get_status_badge()})
                messages.info(request, 'Programarea are deja acest status.')
                return redirect('services:booking_detail', pk=booking.pk)
            log_booking_activity(
                booking,
                'status_changed',
                f'Status schimbat din {dict(Booking.STATUS_CHOICES).get(old_status)} in {booking.get_status_display()}.',
                actor=request.user,
                metadata={'old': old_status, 'new': new_status},
            )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({'ok': True, 'msg': f'Status actualizat: {booking.get_status_display()}', 'status_display': booking.get_status_display(), 'status_badge': booking.get_status_badge()})
            messages.success(request, f'Statusul programarii a fost actualizat la {booking.get_status_display()}.')
            return redirect('services:booking_detail', pk=booking.pk)

    dossier = build_vehicle_dossier(vin=booking.car_vin, plate=booking.car_plate)
    history_entries = [item for item in dossier['history'] if item.pk != booking.pk and item.status == Booking.STATUS_DONE]

    from .models import MechanicWorkLog
    work_log = None
    if booking.mechanic:
        work_log = MechanicWorkLog.objects.filter(booking=booking, mechanic=booking.mechanic).prefetch_related('photos').first()

    job_card_form = JobCardForm(instance=job_card, center=booking.center)
    operation_form = JobOperationForm()
    recommendation_form = JobRecommendationForm()
    part_usage_form = JobPartUsageForm(center=booking.center)

    return render(request, 'services/booking_detail.html', {
        'booking': booking,
        'mechanics': mechanics,
        'history_entries': history_entries,
        'dossier': dossier,
        'job_card': job_card,
        'job_card_form': job_card_form,
        'operation_form': operation_form,
        'recommendation_form': recommendation_form,
        'part_usage_form': part_usage_form,
        'work_log': work_log,
        'activity_logs': booking.activity_logs.all()[:12],
        'checklist_items': booking.checklist_items.all(),
        'operational_tag_choices': Booking.TAG_CHOICES,
        'status_choices': [choice for choice in Booking.STATUS_CHOICES if choice[0] not in [Booking.STATUS_PENDING, Booking.STATUS_QUOTED, Booking.STATUS_CANCELLED]],
    })


@login_required
def booking_print(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('center', 'service_item', 'user', 'garage', 'mechanic').prefetch_related(
            'job_card__operations',
            'job_card__part_usages',
        ),
        pk=pk,
    )
    if not (request.user.is_staff or booking.center.owner_id == request.user.id):
        return redirect('core:home')

    return render(request, 'services/booking_print.html', {
        'booking': booking,
        'work_order_services_text': build_work_order_services_text(booking),
    })


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
            log_booking_activity(
                booking,
                'schedule_changed',
                'Programarea a fost creata direct din dashboardul service-ului.',
                actor=request.user,
            )

            for uploaded in request.FILES.getlist('attachments'):
                uploaded = prepare_uploaded_file(uploaded)
                validate_booking_media_file(uploaded)
                content_type = getattr(uploaded, 'content_type', '') or ''
                media_kind = 'video' if content_type.startswith('video/') else 'image'
                BookingAttachment.objects.create(booking=booking, file=uploaded, media_kind=media_kind)
                log_booking_activity(
                    booking,
                    'attachment_added',
                    f'A fost adaugat un fisier la creare: {sanitize_uploaded_filename(uploaded.name)}.',
                    actor=request.user,
                    metadata={'filename': uploaded.name, 'media_kind': media_kind},
                )

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

        booking.duration_minutes = duration_minutes
        booking.estimated_price = estimated_price
        try:
            booking.full_clean()
            old_status, _, _ = transition_booking_status(booking, Booking.STATUS_QUOTED, actor=request.user)
            booking.save(update_fields=['duration_minutes', 'estimated_price', 'updated_at'])
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return _post_redirect(request, 'services:dashboard')
        log_booking_activity(
            booking,
            'offer_updated',
            f'A fost trimisa o oferta de {estimated_price:.2f} RON cu durata {booking.get_duration_display()}.',
            actor=request.user,
            metadata={'old': old_status, 'new': booking.status, 'estimated_price': estimated_price, 'duration_minutes': duration_minutes},
        )
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
        email_sent = send_booking_quote_email(booking)
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
        try:
            old_status, _, _ = transition_booking_status(booking, Booking.STATUS_CANCELLED, actor=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('services:dashboard')
        log_booking_activity(
            booking,
            'status_changed',
            'Programarea a fost anulata de service inainte de confirmare.',
            actor=request.user,
            metadata={'old': old_status, 'new': Booking.STATUS_CANCELLED},
        )
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
    notifs = BookingNotification.objects.filter(recipient=request.user).select_related('booking')
    page_obj = _paginate_queryset(request, notifs, per_page=20)
    return render(request, 'services/service_notifications.html', {
        'notifications': page_obj.object_list,
        'page_obj': page_obj,
        'total_notifications': notifs.count(),
    })


@login_required
def notifications_feed(request):
    centers = _require_service_owner(request)
    if centers is None:
        return JsonResponse({'ok': False, 'detail': 'service_required'}, status=403)

    unread_count = BookingNotification.objects.filter(recipient=request.user, is_read=False).count()
    latest = list(
        BookingNotification.objects.filter(recipient=request.user)
        .select_related('booking')
        .values('id', 'title', 'created_at', 'is_read')[:5]
    )
    for item in latest:
        item['created_at'] = timezone.localtime(item['created_at']).strftime('%d.%m.%Y %H:%M')

    return JsonResponse({
        'ok': True,
        'unread_count': unread_count,
        'latest_notifications': latest,
    })


@login_required
def notification_mark_read(request, pk):
    notif = get_object_or_404(BookingNotification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return redirect(request.META.get('HTTP_REFERER', 'services:notifications'))


# ===== MECHANIC INTERFACE =====



@login_required
def _legacy_parts_inventory_unused(request):
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

    query = (request.GET.get('q') or '').strip()
    selected_category = (request.GET.get('category') or '').strip()
    selected_stock_status = (request.GET.get('stock_status') or '').strip()
    selected_sort = (request.GET.get('sort') or 'name').strip() or 'name'

    redirect_params = {'center': selected_center.pk}
    if query:
        redirect_params['q'] = query
    if selected_category:
        redirect_params['category'] = selected_category
    if selected_stock_status:
        redirect_params['stock_status'] = selected_stock_status
    if selected_sort and selected_sort != 'name':
        redirect_params['sort'] = selected_sort
    redirect_url = f"{reverse('services:parts_inventory')}?{urlencode(redirect_params)}"

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_part':
            form = ServicePartForm(request.POST)
            if form.is_valid():
                part = form.save(commit=False)
                part.center = selected_center
                part.save()
                messages.success(request, 'Piesa a fost adăugată în stoc.')
                return redirect(redirect_url)
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
                return redirect(redirect_url)
        elif action == 'adjust_stock':
            part = get_object_or_404(ServicePart, pk=request.POST.get('part_id'), center__in=centers)
            try:
                delta = int(request.POST.get('delta', 0))
            except (TypeError, ValueError):
                messages.error(request, 'Actualizarea rapidă a stocului a eșuat.')
            else:
                part.stock = max(part.stock + delta, 0)
                part.save(update_fields=['stock', 'updated_at'])
                messages.success(request, f'Stocul pentru {part.name} a fost actualizat la {part.stock} {part.unit}.')
                return redirect(redirect_url)
        elif action == 'delete_part':
            part = get_object_or_404(ServicePart, pk=request.POST.get('part_id'), center__in=centers)
            part.delete()
            messages.info(request, 'Piesa a fost ștearsă din stoc.')
            return redirect(redirect_url)
    else:
        form = ServicePartForm()

    parts = ServicePart.objects.filter(center=selected_center)
    if query:
        parts = parts.filter(
            Q(name__icontains=query)
            | Q(part_number__icontains=query)
            | Q(brand__icontains=query)
            | Q(supplier__icontains=query)
            | Q(shelf__icontains=query)
            | Q(notes__icontains=query)
        )
    if selected_category:
        parts = parts.filter(category=selected_category)
    if selected_stock_status == 'out':
        parts = parts.filter(stock=0)
    elif selected_stock_status == 'low':
        parts = parts.filter(stock__lte=models.F('minimum_stock')).exclude(stock=0)
    elif selected_stock_status == 'ok':
        parts = parts.filter(stock__gt=models.F('minimum_stock'))

    sort_options = {
        'name': ['name', 'brand'],
        'stock_asc': ['stock', 'name'],
        'stock_desc': ['-stock', 'name'],
        'updated': ['-updated_at', 'name'],
        'price_desc': ['-price', 'name'],
        'category': ['category', 'name'],
    }
    parts = parts.order_by(*sort_options.get(selected_sort, ['name']))
    page_obj = _paginate_queryset(request, parts, per_page=18, page_param='stock_page')
    parts_stats = {
        'total_parts': parts.count(),
        'low_stock_count': parts.filter(stock__lte=models.F('minimum_stock')).count(),
        'out_of_stock_count': parts.filter(stock=0).count(),
        'estimated_stock_value': parts.aggregate(
            total=Sum(
                models.F('stock') * models.F('price'),
                output_field=models.DecimalField(max_digits=14, decimal_places=2),
            )
        )['total'] or Decimal('0.00'),
    }
    return render(request, 'services/parts_inventory.html', {
        'centers': centers,
        'selected_center': selected_center,
        'parts': page_obj.object_list,
        'page_obj': page_obj,
        'form': form,
        'low_stock_count': parts_stats['low_stock_count'],
        'parts_stats': parts_stats,
        'selected_query': query,
        'selected_category': selected_category,
        'selected_stock_status': selected_stock_status,
        'selected_sort': selected_sort,
        'category_filters': ServicePart.CATEGORY_FILTERS,
    })


@login_required
def _legacy_service_car_history_unused(request):
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
        mechanic=mechanic,
        status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_IN_PROGRESS, Booking.STATUS_WAITING_PARTS],
    ).select_related('center', 'service_item', 'garage').order_by('booking_date', 'booking_time')

    done_bookings = Booking.objects.filter(
        mechanic=mechanic, status=Booking.STATUS_DONE
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
                try:
                    validate_image_file(photo, label='Fotografia de lucru')
                except ValidationError as exc:
                    messages.error(request, exc.message)
                    return redirect('services:mechanic_profile', pk=pk)
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
                if booking.status == new_status:
                    messages.info(request, 'Programarea are deja acest status.')
                    return redirect('services:mechanic_profile', pk=pk)
                try:
                    old_status, _, _ = transition_booking_status(
                        booking,
                        new_status,
                        actor=request.user,
                        sync_job_card=True,
                        create_job_card=True,
                    )
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                    return redirect('services:mechanic_profile', pk=pk)
                log_booking_activity(
                    booking,
                    'status_changed',
                    f'Status schimbat din {dict(Booking.STATUS_CHOICES).get(old_status)} in {booking.get_status_display()} din profilul mecanicului.',
                    actor=request.user,
                    metadata={'old': old_status, 'new': new_status},
                )
                sms_sent = False
                email_sent = False
                if new_status == 'in_progress':
                    wl, _ = MechanicWorkLog.objects.get_or_create(booking=booking, mechanic=mechanic)
                    if not wl.started_at:
                        from django.utils import timezone
                        wl.started_at = timezone.now()
                        wl.save(update_fields=['started_at'])
                    email_sent = send_booking_started_email(booking)
                    sms_sent = send_booking_started_sms(booking)
                if new_status == 'done':
                    wl, _ = MechanicWorkLog.objects.get_or_create(booking=booking, mechanic=mechanic)
                    from django.utils import timezone
                    wl.finished_at = timezone.now()
                    wl.save(update_fields=['finished_at'])
                    email_sent = send_booking_completed_email(booking)
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


@login_required
def parts_inventory(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')
    centers = centers.order_by('name')

    center_id = (request.GET.get('center') or request.POST.get('center_id') or '').strip()
    selected_center = centers.filter(pk=center_id).first() if center_id else centers.first()
    if selected_center is None:
        messages.info(request, 'Adauga mai intai un service pentru a gestiona piesele.')
        return redirect('services:register_service')

    query = (request.GET.get('q') or '').strip()
    selected_category = (request.GET.get('category') or '').strip()
    selected_stock_status = (request.GET.get('stock_status') or '').strip()
    selected_sort = (request.GET.get('sort') or 'name').strip() or 'name'

    redirect_params = {'center': selected_center.pk}
    if query:
        redirect_params['q'] = query
    if selected_category:
        redirect_params['category'] = selected_category
    if selected_stock_status:
        redirect_params['stock_status'] = selected_stock_status
    if selected_sort and selected_sort != 'name':
        redirect_params['sort'] = selected_sort
    redirect_url = f"{reverse('services:parts_inventory')}?{urlencode(redirect_params)}"

    form = ServicePartForm()
    movement_form = StockMovementForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_part':
            form = ServicePartForm(request.POST)
            if form.is_valid():
                part = form.save(commit=False)
                part.center = selected_center
                part.save()
                messages.success(request, 'Piesa a fost adaugata in stoc.')
                return redirect(redirect_url)
        elif action == 'update_stock':
            part = get_object_or_404(ServicePart, pk=request.POST.get('part_id'), center__in=centers)
            try:
                stock = int(request.POST.get('stock', part.stock))
                minimum_stock = int(request.POST.get('minimum_stock', part.minimum_stock))
            except (TypeError, ValueError):
                messages.error(request, 'Valorile pentru stoc trebuie sa fie numere intregi.')
            else:
                target_stock = max(stock, 0)
                delta = target_stock - part.stock
                if delta:
                    try:
                        apply_stock_movement(
                            part,
                            delta,
                            StockMovement.TYPE_ADJUSTMENT,
                            actor=request.user,
                            note='Actualizare manuala din inventar',
                        )
                    except ValidationError as exc:
                        messages.error(request, '; '.join(exc.messages))
                        return redirect(redirect_url)
                part.minimum_stock = max(minimum_stock, 0)
                part.save(update_fields=['stock', 'minimum_stock', 'updated_at'])
                messages.success(request, 'Stocul piesei a fost actualizat.')
                return redirect(redirect_url)
        elif action == 'adjust_stock':
            part = get_object_or_404(ServicePart, pk=request.POST.get('part_id'), center__in=centers)
            try:
                delta = int(request.POST.get('delta', 0))
            except (TypeError, ValueError):
                messages.error(request, 'Actualizarea rapida a stocului a esuat.')
            else:
                try:
                    apply_stock_movement(
                        part,
                        delta,
                        StockMovement.TYPE_ADJUSTMENT,
                        actor=request.user,
                        note='Actualizare rapida din inventar',
                    )
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                    return redirect(redirect_url)
                messages.success(request, f'Stocul pentru {part.name} a fost actualizat la {part.stock} {part.unit}.')
                return redirect(redirect_url)
        elif action == 'record_movement':
            movement_form = StockMovementForm(request.POST)
            if movement_form.is_valid():
                part = get_object_or_404(ServicePart, pk=movement_form.cleaned_data['part_id'], center__in=centers)
                movement_type = movement_form.cleaned_data['movement_type']
                quantity = movement_form.cleaned_data['quantity']
                quantity_delta = quantity if movement_type in {StockMovement.TYPE_IN, StockMovement.TYPE_RELEASE, StockMovement.TYPE_ADJUSTMENT} else -quantity
                try:
                    apply_stock_movement(
                        part,
                        quantity_delta,
                        movement_type,
                        actor=request.user,
                        note=movement_form.cleaned_data['note'],
                    )
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                else:
                    messages.success(request, f'Miscarea pentru {part.name} a fost inregistrata.')
                    return redirect(redirect_url)
        elif action == 'delete_part':
            part = get_object_or_404(ServicePart, pk=request.POST.get('part_id'), center__in=centers)
            part.delete()
            messages.info(request, 'Piesa a fost stearsa din stoc.')
            return redirect(redirect_url)

    parts = ServicePart.objects.filter(center=selected_center)
    if query:
        parts = parts.filter(
            Q(name__icontains=query)
            | Q(part_number__icontains=query)
            | Q(brand__icontains=query)
            | Q(supplier__icontains=query)
            | Q(shelf__icontains=query)
            | Q(notes__icontains=query)
        )
    if selected_category:
        parts = parts.filter(category=selected_category)
    if selected_stock_status == 'out':
        parts = parts.filter(stock=0)
    elif selected_stock_status == 'low':
        parts = parts.filter(stock__lte=models.F('minimum_stock')).exclude(stock=0)
    elif selected_stock_status == 'ok':
        parts = parts.filter(stock__gt=models.F('minimum_stock'))

    sort_options = {
        'name': ['name', 'brand'],
        'stock_asc': ['stock', 'name'],
        'stock_desc': ['-stock', 'name'],
        'updated': ['-updated_at', 'name'],
        'price_desc': ['-sale_price', '-price', 'name'],
        'category': ['category', 'name'],
    }
    parts = parts.order_by(*sort_options.get(selected_sort, ['name']))
    page_obj = _paginate_queryset(request, parts, per_page=18, page_param='stock_page')

    parts_stats = {
        'total_parts': parts.count(),
        'low_stock_count': parts.filter(stock__lte=models.F('minimum_stock')).count(),
        'out_of_stock_count': parts.filter(stock=0).count(),
        'estimated_stock_value': parts.aggregate(
            total=Sum(
                models.F('stock') * models.functions.Coalesce('purchase_price', 'price'),
                output_field=models.DecimalField(max_digits=14, decimal_places=2),
            )
        )['total'] or Decimal('0.00'),
    }
    recent_movements = StockMovement.objects.filter(part__center=selected_center).select_related(
        'part', 'job_card', 'booking', 'actor'
    ).order_by('-created_at')[:12]

    return render(request, 'services/parts_inventory.html', {
        'centers': centers,
        'selected_center': selected_center,
        'parts': page_obj.object_list,
        'page_obj': page_obj,
        'form': form,
        'movement_form': movement_form,
        'recent_movements': recent_movements,
        'low_stock_count': parts_stats['low_stock_count'],
        'parts_stats': parts_stats,
        'selected_query': query,
        'selected_category': selected_category,
        'selected_stock_status': selected_stock_status,
        'selected_sort': selected_sort,
        'category_filters': ServicePart.CATEGORY_FILTERS,
    })


@login_required
def service_car_history(request):
    centers = _require_service_owner(request)
    if centers is None:
        return redirect('services:register_service')

    search = (request.GET.get('q') or '').strip()
    bookings = Booking.objects.filter(center__in=centers).exclude(status=Booking.STATUS_CANCELLED).select_related(
        'center', 'mechanic'
    ).order_by('-booking_date', '-booking_time', '-created_at')
    if search:
        bookings = bookings.filter(
            Q(car_plate__icontains=search)
            | Q(car_vin__icontains=search)
            | Q(car_brand__icontains=search)
            | Q(car_model__icontains=search)
            | Q(client_name__icontains=search)
            | Q(client_phone__icontains=search)
        )

    vehicle_map = {}
    for booking in bookings:
        key = booking.car_vin or booking.car_plate
        if not key:
            continue
        if key not in vehicle_map:
            dossier = build_vehicle_dossier(vin=booking.car_vin, plate=booking.car_plate)
            vehicle_map[key] = {
                'booking': booking,
                'dossier': dossier,
                'summary': dossier['summary'],
                'open_recommendations': dossier['open_recommendations'][:3],
            }

    vehicles = list(vehicle_map.values())
    return render(request, 'services/car_history.html', {
        'vehicles': vehicles,
        'centers': centers,
        'search': search,
    })
