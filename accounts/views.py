from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from services.models import Favorite
from .forms import RegisterForm, LoginForm, CarForm
from .models import Car


def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Bun venit, {user.first_name}! Contul tău a fost creat.')
            return redirect('core:home')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bun venit înapoi, {user.first_name or user.username}!')
            next_url = request.GET.get('next', 'core:home')
            return redirect(next_url)
    else:
        form = LoginForm(request)
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Ai fost deconectat.')
    return redirect('core:home')


@login_required
def profile(request):
    from bookings.models import Booking
    bookings = Booking.objects.filter(user=request.user).select_related(
        'center', 'center__category'
    ).order_by('-created_at')
    favorites = Favorite.objects.filter(user=request.user).select_related(
        'center', 'center__category'
    ).order_by('-created_at')
    cars = Car.objects.filter(owner=request.user).order_by('make', 'model', 'plate_number')
    return render(request, 'accounts/profile.html', {
        'bookings': bookings,
        'favorites': favorites,
        'cars': cars,
    })


@login_required
def car_list(request):
    cars = Car.objects.filter(owner=request.user).order_by('make', 'model', 'plate_number')
    return render(request, 'accounts/car_list.html', {'cars': cars})


@login_required
def car_create(request):
    if request.method == 'POST':
        form = CarForm(request.POST)
        if form.is_valid():
            car = form.save(commit=False)
            car.owner = request.user
            car.save()
            messages.success(request, '✅ Mașina a fost adăugată în cont.')
            next_url = request.GET.get('next')
            return redirect(next_url or 'accounts:cars')
    else:
        form = CarForm()
    return render(request, 'accounts/car_form.html', {
        'form': form,
        'mode': 'create',
    })


@login_required
def car_update(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = CarForm(request.POST, instance=car)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Mașina a fost actualizată.')
            next_url = request.GET.get('next')
            return redirect(next_url or 'accounts:cars')
    else:
        form = CarForm(instance=car)
    return render(request, 'accounts/car_form.html', {
        'form': form,
        'mode': 'update',
        'car': car,
    })


@login_required
def car_delete(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)
    if request.method == 'POST':
        car.delete()
        messages.info(request, 'Mașina a fost ștearsă.')
        next_url = request.GET.get('next')
        return redirect(next_url or 'accounts:cars')
    return render(request, 'accounts/car_confirm_delete.html', {'car': car})
