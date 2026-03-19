from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.db.models import Avg, Count, Q
from services.models import ServiceCategory, ServiceCenter, CITY_CHOICES


def home(request):
    if request.user.is_authenticated and ServiceCenter.objects.filter(owner=request.user).exists():
        return redirect('services:dashboard')

    categories = ServiceCategory.objects.annotate(
        center_count=Count('servicecenter', filter=Q(servicecenter__is_active=True))
    ).order_by('order')

    featured = ServiceCenter.objects.filter(is_active=True, is_featured=True).annotate(
        avg_rating=Avg('review__rating', filter=Q(review__is_approved=True)),
        review_count=Count('review', filter=Q(review__is_approved=True)),
    ).order_by('-avg_rating')[:6]

    total_centers = ServiceCenter.objects.filter(is_active=True).count()
    total_cities = ServiceCenter.objects.filter(is_active=True).values('city').distinct().count()

    context = {
        'categories': categories,
        'featured': featured,
        'cities': CITY_CHOICES,
        'total_centers': total_centers,
        'total_cities': total_cities,
    }
    return render(request, 'core/home.html', context)


def about(request):
    return render(request, 'core/about.html')



def terms(request):
    return render(request, "legal/terms.html")


def privacy(request):
    return render(request, "legal/privacy.html")


def cookies(request):
    return render(request, "legal/cookies.html")
