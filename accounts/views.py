from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.dateparse import parse_date

from services.models import Favorite
from .forms import RegisterForm, LoginForm, CarForm, CarExpiryProfileForm
from .models import Car, CarExpiryProfile


STAR_POSITIONS = [
    {'key': 'itp', 'top': '14%', 'left': '50%'},
    {'key': 'rca', 'top': '33%', 'left': '77%'},
    {'key': 'rovinieta', 'top': '76%', 'left': '65%'},
    {'key': 'casco', 'top': '76%', 'left': '35%'},
    {'key': 'siguranta_auto', 'top': '33%', 'left': '23%'},
]


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
    cars = list(Car.objects.filter(owner=request.user).order_by('make', 'model', 'plate_number'))

    for car in cars:
        expiry_profile = getattr(car, 'expiry_profile', None)
        car.expiry_badge = expiry_profile.get_dashboard_badge() if expiry_profile else {
            'label': 'Nesetat',
            'class': 'secondary',
            'icon': 'bi-dash-circle',
        }

    return render(request, 'accounts/profile.html', {
        'bookings': bookings,
        'favorites': favorites,
        'cars': cars,
    })


@login_required
def car_list(request):
    cars = list(Car.objects.filter(owner=request.user).order_by('make', 'model', 'plate_number'))
    for car in cars:
        expiry_profile = getattr(car, 'expiry_profile', None)
        car.expiry_badge = expiry_profile.get_dashboard_badge() if expiry_profile else {
            'label': 'Nesetat',
            'class': 'secondary',
            'icon': 'bi-dash-circle',
        }
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


def _pick_worst_status(*items):
    priority = {
        CarExpiryProfile.STATUS_EXPIRED: 3,
        CarExpiryProfile.STATUS_SOON: 2,
        CarExpiryProfile.STATUS_MISSING: 1,
        CarExpiryProfile.STATUS_OK: 0,
    }
    valid_items = [item for item in items if item]
    if not valid_items:
        return CarExpiryProfile.STATUS_MISSING
    return max(valid_items, key=lambda item: priority[item['status']])['status']


SECTION_FIELDS = {
    'itp': ['itp_expiry'],
    'rca': ['rca_expiry'],
    'rovinieta': ['rovinieta_expiry'],
    'casco': ['casco_expiry'],
    'siguranta_auto': ['trusa_expiry', 'extinctor_expiry'],
}


@login_required
def car_expiry_calendar(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)
    expiry_profile, _ = CarExpiryProfile.objects.get_or_create(car=car)

    active_section = request.GET.get('section', '')

    if request.method == 'POST':
        active_section = request.POST.get('active_section', '')
        changed_fields = SECTION_FIELDS.get(active_section, [])
        form = CarExpiryProfileForm(instance=expiry_profile)

        if not changed_fields:
            messages.error(request, 'Categoria selectată nu este validă.')
        else:
            posted_values = {}
            field_errors = []

            for field_name in changed_fields:
                raw_value = (request.POST.get(field_name) or '').strip()
                if not raw_value:
                    posted_values[field_name] = None
                    continue

                parsed_value = parse_date(raw_value)
                if parsed_value is None:
                    field_label = form.fields[field_name].label or field_name
                    field_errors.append(f'{field_label}: data introdusă nu este validă.')
                else:
                    posted_values[field_name] = parsed_value

            if field_errors:
                for error in field_errors:
                    messages.error(request, error)
            else:
                for field_name, value in posted_values.items():
                    setattr(expiry_profile, field_name, value)
                if posted_values:
                    expiry_profile.save(update_fields=[*posted_values.keys(), 'updated_at'])
                messages.success(request, 'Calendarul de expirări a fost actualizat.')
                redirect_url = f"{redirect('accounts:car_calendar', pk=car.pk).url}?section={active_section or 'itp'}"
                return redirect(redirect_url)
    else:
        form = CarExpiryProfileForm(instance=expiry_profile)

    items_by_field = {item['field']: item for item in expiry_profile.get_document_items()}
    counts = expiry_profile.get_status_counts()

    node_map = {
        'itp': {
            'key': 'itp',
            'label': 'ITP',
            'icon': 'bi-shield-check',
            'status': items_by_field['itp_expiry']['status'],
            'date': items_by_field['itp_expiry']['date'],
            'days_left': items_by_field['itp_expiry']['days_left'],
            'days_overdue': items_by_field['itp_expiry']['days_overdue'],
            'description': 'Inspecția tehnică periodică a mașinii.',
        },
        'rca': {
            'key': 'rca',
            'label': 'RCA',
            'icon': 'bi-file-earmark-text',
            'status': items_by_field['rca_expiry']['status'],
            'date': items_by_field['rca_expiry']['date'],
            'days_left': items_by_field['rca_expiry']['days_left'],
            'days_overdue': items_by_field['rca_expiry']['days_overdue'],
            'description': 'Asigurarea obligatorie a vehiculului.',
        },
        'rovinieta': {
            'key': 'rovinieta',
            'label': 'Rovinietă',
            'icon': 'bi-sign-turn-right',
            'status': items_by_field['rovinieta_expiry']['status'],
            'date': items_by_field['rovinieta_expiry']['date'],
            'days_left': items_by_field['rovinieta_expiry']['days_left'],
            'days_overdue': items_by_field['rovinieta_expiry']['days_overdue'],
            'description': 'Valabilitatea rovinietei pentru drumurile naționale.',
        },
        'casco': {
            'key': 'casco',
            'label': 'CASCO',
            'icon': 'bi-shield-shaded',
            'status': items_by_field['casco_expiry']['status'],
            'date': items_by_field['casco_expiry']['date'],
            'days_left': items_by_field['casco_expiry']['days_left'],
            'days_overdue': items_by_field['casco_expiry']['days_overdue'],
            'description': 'Asigurarea facultativă a mașinii.',
        },
        'siguranta_auto': {
            'key': 'siguranta_auto',
            'label': 'Siguranță auto',
            'icon': 'bi-shield-plus',
            'status': _pick_worst_status(items_by_field['trusa_expiry'], items_by_field['extinctor_expiry']),
            'date': None,
            'days_left': None,
            'days_overdue': 0,
            'description': 'Include trusa auto și extinctorul.',
            'subitems': [items_by_field['trusa_expiry'], items_by_field['extinctor_expiry']],
        },
    }

    star_nodes = []
    for position in STAR_POSITIONS:
        node = position.copy()
        node.update(node_map[position['key']])
        star_nodes.append(node)

    if active_section not in node_map:
        active_section = ''

    return render(request, 'accounts/car_calendar.html', {
        'car': car,
        'form': form,
        'expiry_profile': expiry_profile,
        'star_nodes': star_nodes,
        'status_counts': counts,
        'active_section': active_section,
    })
