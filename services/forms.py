import requests
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP

from .models import ServiceCenter, ServiceCategory, ServiceGarage, ServiceImage, Review


def geocodeaza_adresa(address, city_display):
    """
    Apeleaza Nominatim (OpenStreetMap, gratuit) si returneaza (Decimal, Decimal) sau (None, None).
    Coordonatele sunt intotdeauna cu PUNCT ca separator zecimal.
    """
    try:
        query = f"{address}, {city_display}, Romania"
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "AutoHub/1.0"},
            timeout=5,
        )
        results = resp.json()
        if results:
            # float() garanteaza punct indiferent de locala sistemului
            lat = Decimal(str(float(results[0]["lat"]))).quantize(Decimal('0.0000001'), rounding=ROUND_HALF_UP)
            lng = Decimal(str(float(results[0]["lon"]))).quantize(Decimal('0.0000001'), rounding=ROUND_HALF_UP)
            return lat, lng
    except Exception:
        pass
    return None, None


class ServiceCenterRegisterForm(forms.ModelForm):
    """Form standard (din cont) pentru înregistrarea unui service."""

    categories = forms.ModelMultipleChoiceField(
        label='Categorii disponibile',
        queryset=ServiceCategory.objects.order_by('order', 'name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    all_categories = forms.BooleanField(
        required=False,
        label='Toate categoriile',
    )

    class Meta:
        model = ServiceCenter
        fields = [
            'name', 'description', 'address', 'city', 'phone', 'email',
            'website', 'schedule', 'card_image', 'legal_name', 'headquarters',
            'fiscal_code', 'trade_register_no', 'legal_document',
            'latitude', 'longitude',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Service Auto X'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Str. Mihai Eminescu 10',
                'id': 'id_address',
                'autocomplete': 'off',
            }),
            'city': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'schedule': forms.TextInput(attrs={'class': 'form-control'}),
            'card_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'legal_name': forms.TextInput(attrs={'class': 'form-control'}),
            'headquarters': forms.TextInput(attrs={'class': 'form-control'}),
            'fiscal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'trade_register_no': forms.TextInput(attrs={'class': 'form-control'}),
            'legal_document': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            existing = self.instance.categories.all()
            if existing.exists():
                self.fields['categories'].initial = existing
            elif self.instance.category_id:
                self.fields['categories'].initial = [self.instance.category_id]

    def _any_legal_data(self, cleaned):
        return any([
            (cleaned.get('legal_name') or '').strip(),
            (cleaned.get('headquarters') or '').strip(),
            (cleaned.get('fiscal_code') or '').strip(),
            (cleaned.get('trade_register_no') or '').strip(),
        ])

    def clean_latitude(self):
        val = self.cleaned_data.get('latitude')
        if val is not None:
            # float() + str() = garantat punct ca separator, indiferent de locala
            return Decimal(str(float(val))).quantize(Decimal('0.0000001'), rounding=ROUND_HALF_UP)
        return val

    def clean_longitude(self):
        val = self.cleaned_data.get('longitude')
        if val is not None:
            return Decimal(str(float(val))).quantize(Decimal('0.0000001'), rounding=ROUND_HALF_UP)
        return val

    def clean(self):
        cleaned = super().clean()
        any_legal = self._any_legal_data(cleaned)
        doc = cleaned.get('legal_document')
        categories = cleaned.get('categories')
        if cleaned.get('all_categories'):
            categories = self.fields['categories'].queryset
            cleaned['categories'] = categories
        if any_legal and not doc and not getattr(self.instance, 'legal_document', None):
            self.add_error(
                'legal_document',
                'Dacă ai completat datele legale, încarcă și un document care să ateste deținerea firmei.'
            )
        if not categories:
            self.add_error('categories', 'Selectează cel puțin o categorie sau bifează „Toate categoriile".')
        return cleaned

    def save(self, commit=True):
        center = super().save(commit=False)

        selected_categories = self.cleaned_data.get('categories')
        if self.cleaned_data.get('all_categories'):
            selected_categories = self.fields['categories'].queryset

        primary_category = selected_categories.first() if selected_categories is not None else None
        if primary_category:
            center.category = primary_category

        any_legal = self._any_legal_data(self.cleaned_data)
        if any_legal:
            center.verification_status = 'pending'
            center.is_active = False
        else:
            center.verification_status = 'not_required'
            center.is_active = True

        # Geocoding automat — fallback daca harta nu a setat coordonatele
        if not center.latitude or not center.longitude:
            lat, lng = geocodeaza_adresa(center.address, center.get_city_display())
            if lat and lng:
                center.latitude = lat
                center.longitude = lng

        if commit:
            center.save()
            if selected_categories is not None:
                center.categories.set(selected_categories)
        else:
            self._pending_categories = selected_categories
        return center

    def save_m2m(self):
        super().save_m2m()
        if hasattr(self, '_pending_categories') and self.instance.pk and self._pending_categories is not None:
            self.instance.categories.set(self._pending_categories)


class ServiceCenterPublicRegisterForm(ServiceCenterRegisterForm):
    """Înregistrare service fără login: creează și contul proprietarului."""

    owner_first_name = forms.CharField(
        label='Prenume',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    owner_last_name = forms.CharField(
        label='Nume',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    owner_email = forms.EmailField(
        label='Email (cont proprietar)',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    password1 = forms.CharField(
        label='Parolă',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    password2 = forms.CharField(
        label='Confirmă parola',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def clean_owner_email(self):
        email = (self.cleaned_data.get('owner_email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                'Există deja un cont cu acest email. Te rog autentifică-te și înregistrează service-ul din cont.'
            )
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Parolele nu coincid.')
        if p1:
            try:
                validate_password(p1)
            except ValidationError as e:
                self.add_error('password1', e)
        return cleaned

    def save(self, commit=True):
        email = self.cleaned_data['owner_email'].strip().lower()
        username_base = email.split('@')[0]
        username = username_base
        n = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{username_base}{n}"
            n += 1

        user = User(
            username=username,
            email=email,
            first_name=(self.cleaned_data.get('owner_first_name') or '').strip(),
            last_name=(self.cleaned_data.get('owner_last_name') or '').strip(),
        )
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()

        center = super(ServiceCenterRegisterForm, self).save(commit=False)
        center.owner = user

        selected_categories = self.cleaned_data.get('categories')
        if self.cleaned_data.get('all_categories'):
            selected_categories = self.fields['categories'].queryset
        primary_category = selected_categories.first() if selected_categories is not None else None
        if primary_category:
            center.category = primary_category

        any_legal = self._any_legal_data(self.cleaned_data)
        if any_legal:
            center.verification_status = 'pending'
            center.is_active = False
        else:
            center.verification_status = 'not_required'
            center.is_active = True

        # Geocoding automat — fallback
        if not center.latitude or not center.longitude:
            lat, lng = geocodeaza_adresa(center.address, center.get_city_display())
            if lat and lng:
                center.latitude = lat
                center.longitude = lng

        if commit:
            center.save()
            if selected_categories is not None:
                center.categories.set(selected_categories)

        return center, user


class ServiceGarageForm(forms.ModelForm):
    class Meta:
        model = ServiceGarage
        fields = ['name', 'category', 'open_time', 'close_time', 'slot_minutes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Elevator 1 / Garaj rapid'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'open_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'close_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'slot_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 15, 'step': 15}),
        }

    def __init__(self, *args, **kwargs):
        self.center = kwargs.pop('center', None)
        super().__init__(*args, **kwargs)

        queryset = ServiceCategory.objects.none()
        if self.center is not None:
            queryset = self.center.categories.all()
            if not queryset.exists() and self.center.category_id:
                queryset = ServiceCategory.objects.filter(pk=self.center.category_id)

        self.fields['category'].queryset = queryset

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get('category')

        if self.center is None:
            raise forms.ValidationError('Nu a fost transmis service-ul pentru acest garaj.')

        allowed_ids = set(self.center.categories.values_list('id', flat=True))
        if not allowed_ids and self.center.category_id:
            allowed_ids.add(self.center.category_id)

        if category and category.id not in allowed_ids:
            self.add_error('category', 'Poți alege doar o categorie din cele selectate de service.')

        return cleaned


class ServiceGalleryImageForm(forms.ModelForm):
    class Meta:
        model = ServiceImage
        fields = ['image', 'caption']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Recepție / Intrare / Atelier'}),
        }

class MultiImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class ReviewForm(forms.ModelForm):
    images = forms.FileField(
        required=False,
        widget=MultiImageInput(attrs={'class': 'form-control', 'multiple': True, 'accept': 'image/*'}),
        help_text='Poți încărca până la 5 poze.'
    )

    class Meta:
        model = Review
        fields = ['rating', 'title', 'body']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titlu scurt pentru experiența ta'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Cum a fost experiența la acest service?'}),
        }

    def clean_images(self):
        files = self.files.getlist('images')
        if len(files) > 5:
            raise forms.ValidationError('Poți încărca maximum 5 poze la o recenzie.')
        for uploaded in files:
            content_type = getattr(uploaded, 'content_type', '') or ''
            if not content_type.startswith('image/'):
                raise forms.ValidationError(f'{uploaded.name} nu este o imagine.')
        return files
