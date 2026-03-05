from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Min, Max, Q
from .models import ServiceCategory, ServiceCenter, ServiceItem, Review, Favorite


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
