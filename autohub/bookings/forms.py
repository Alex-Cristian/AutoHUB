from django import forms
from django.utils import timezone

from .models import Booking
from services.models import ServiceItem, ServiceGarage
from accounts.models import Car


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class BookingForm(forms.ModelForm):
    saved_car = forms.ModelChoiceField(
        queryset=Car.objects.none(),
        required=False,
        empty_label='— Alege o mașină salvată (opțional) —',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_saved_car'})
    )
    attachments = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={'class': 'form-control', 'accept': 'image/*,video/*', 'multiple': True}),
        help_text='Poți încărca poze și video cu problema mașinii.'
    )

    class Meta:
        model = Booking
        fields = [
            'client_name', 'client_phone', 'client_email',
            'car_brand', 'car_model', 'car_year', 'car_fuel', 'car_plate',
            'service_item', 'garage', 'problem_description',
            'booking_date', 'booking_time',
        ]
        widgets = {
            'client_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: Ion Popescu'}),
            'client_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: 0722 123 456'}),
            'client_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ex: ion@email.ro'}),
            'car_brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: Dacia, Volkswagen, BMW'}),
            'car_model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: Logan, Golf, Seria 3'}),
            'car_year': forms.NumberInput(attrs={'class': 'form-control', 'min': 1950, 'placeholder': 'ex: 2018'}),
            'car_fuel': forms.Select(attrs={'class': 'form-select'}),
            'car_plate': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: B 123 ABC', 'style': 'text-transform:uppercase'}),
            'service_item': forms.Select(attrs={'class': 'form-select'}),
            'garage': forms.Select(attrs={'class': 'form-select'}),
            'problem_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descrieți problema sau serviciul dorit...'}),
            'booking_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'booking_time': forms.HiddenInput(),
        }

    def __init__(self, center=None, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.center = center
        if center:
            self.fields['service_item'].queryset = ServiceItem.objects.filter(center=center)
            self.fields['service_item'].empty_label = '— Selectați un serviciu (opțional) —'
            self.fields['garage'].queryset = ServiceGarage.objects.filter(center=center).order_by('name')
            self.fields['garage'].empty_label = '— Alege un garaj —'
        if user and user.is_authenticated:
            self.fields['saved_car'].queryset = Car.objects.filter(owner=user).order_by('make', 'model', 'plate_number')
            self.fields['client_name'].initial = user.get_full_name() or user.username
            self.fields['client_email'].initial = user.email
        else:
            self.fields['saved_car'].widget = forms.HiddenInput()

        today = timezone.now().date()
        self.fields['booking_date'].widget.attrs['min'] = str(today)

    def clean(self):
        cleaned = super().clean()
        saved_car = cleaned.get('saved_car')
        garage = cleaned.get('garage')
        booking_date = cleaned.get('booking_date')
        booking_time = cleaned.get('booking_time')
        if saved_car:
            cleaned['car_brand'] = saved_car.make
            cleaned['car_model'] = saved_car.model
            cleaned['car_year'] = saved_car.year or cleaned.get('car_year')
            if saved_car.fuel:
                cleaned['car_fuel'] = saved_car.fuel
            cleaned['car_plate'] = saved_car.plate_number

        if self.center and garage and garage.center_id != self.center.id:
            self.add_error('garage', 'Garajul selectat nu aparține acestui service.')

        if garage and booking_date and booking_time and not garage.is_time_available(booking_date, booking_time):
            self.add_error('booking_time', 'Ora aleasă nu mai este disponibilă pentru garajul selectat.')

        attachments = self.files.getlist('attachments')
        for uploaded in attachments:
            content_type = getattr(uploaded, 'content_type', '') or ''
            if not (content_type.startswith('image/') or content_type.startswith('video/')):
                self.add_error('attachments', f'Fișierul {uploaded.name} nu este imagine sau video.')
            if uploaded.size > 50 * 1024 * 1024:
                self.add_error('attachments', f'Fișierul {uploaded.name} depășește limita de 50MB.')

        return cleaned

    def clean_booking_date(self):
        date = self.cleaned_data.get('booking_date')
        if date and date < timezone.now().date():
            raise forms.ValidationError('Data programării nu poate fi în trecut.')
        return date

    def clean_car_year(self):
        year = self.cleaned_data.get('car_year')
        current_year = timezone.now().year
        if year and (year < 1950 or year > current_year + 1):
            raise forms.ValidationError(f'Anul mașinii trebuie să fie între 1950 și {current_year + 1}.')
        return year

    def clean_car_plate(self):
        plate = (self.cleaned_data.get('car_plate') or '').upper().strip()
        if not plate:
            raise forms.ValidationError('Introduceți numărul de înmatriculare.')
        return plate
