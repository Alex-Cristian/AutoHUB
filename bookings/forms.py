from django import forms
from django.utils import timezone

from .ai import normalize_duration_minutes
from .models import Booking
from services.models import ServiceItem, ServiceGarage
from accounts.models import Car
from core.upload_validators import validate_booking_media_file


WEEKDAY_LABELS = {
    0: 'luni',
    1: 'marti',
    2: 'miercuri',
    3: 'joi',
    4: 'vineri',
    5: 'sambata',
    6: 'duminica',
}


def service_open_weekdays(schedule_text: str) -> set[int]:
    text = (schedule_text or '').strip().lower()
    if not text:
        return {0, 1, 2, 3, 4}
    if 'non-stop' in text or '24/7' in text or '24h' in text:
        return {0, 1, 2, 3, 4, 5, 6}

    weekdays = {0, 1, 2, 3, 4} if 'lun-vin' in text else set()
    if 'lun-sam' in text:
        weekdays.update({0, 1, 2, 3, 4, 5})
    if 'lun-dum' in text:
        weekdays.update({0, 1, 2, 3, 4, 5, 6})
    if 'sam' in text:
        weekdays.add(5)
    if 'dum' in text:
        weekdays.add(6)
    return weekdays or {0, 1, 2, 3, 4}


class MultiFileInput(forms.FileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        return files.getlist(name)


class MultipleFileField(forms.Field):
    widget = MultiFileInput(attrs={
        'class': 'form-control',
        'accept': 'image/*,video/*',
        'multiple': True,
    })

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            return []
        return [f for f in data if f]


class BookingForm(forms.ModelForm):
    preferred_date_2 = forms.DateField(
        required=False,
        label='A doua preferinta - data',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    preferred_time_2 = forms.TimeField(
        required=False,
        label='A doua preferinta - ora',
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
    )
    preferred_date_3 = forms.DateField(
        required=False,
        label='A treia preferinta - data',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    preferred_time_3 = forms.TimeField(
        required=False,
        label='A treia preferinta - ora',
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
    )
    saved_car = forms.ModelChoiceField(
        queryset=Car.objects.none(),
        required=False,
        empty_label='- Alege o masina salvata (optional) -',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_saved_car'})
    )
    attachments = MultipleFileField(
        help_text='Poti incarca poze sau video utile pentru analiza cererii.'
    )

    class Meta:
        model = Booking
        fields = [
            'client_name', 'client_phone', 'client_email',
            'car_brand', 'car_model', 'car_year', 'car_fuel', 'car_plate', 'car_vin',
            'service_item', 'garage', 'problem_description',
            'booking_date', 'booking_time',
            'preferred_date_2', 'preferred_time_2', 'preferred_date_3', 'preferred_time_3',
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
            'car_vin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: UU1KSD0F554433221', 'style': 'text-transform:uppercase'}),
            'service_item': forms.Select(attrs={'class': 'form-select'}),
            'garage': forms.Select(attrs={'class': 'form-select'}),
            'problem_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descrieti pe scurt problema si serviciul dorit...', 'data-duration-source': 'problem-description'}),
            'booking_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'booking_time': forms.HiddenInput(),
        }

    def __init__(self, center=None, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.center = center
        self.allowed_weekdays = service_open_weekdays(getattr(center, 'schedule', '')) if center else {0, 1, 2, 3, 4}
        if center:
            self.fields['service_item'].queryset = ServiceItem.objects.filter(center=center)
            self.fields['service_item'].empty_label = '- Selecteaza un serviciu (optional) -'
            self.fields['garage'].queryset = ServiceGarage.objects.filter(center=center).order_by('name')
            self.fields['garage'].empty_label = '- Alege un post preferat (optional) -'
        if user and user.is_authenticated:
            self.fields['saved_car'].queryset = Car.objects.filter(owner=user).order_by('make', 'model', 'plate_number')
            self.fields['client_name'].initial = user.get_full_name() or user.username
            self.fields['client_email'].initial = user.email
        else:
            self.fields['saved_car'].widget = forms.HiddenInput()

        today = timezone.now().date()
        self.fields['booking_date'].widget.attrs['min'] = str(today)
        self.fields['preferred_date_2'].widget.attrs['min'] = str(today)
        self.fields['preferred_date_3'].widget.attrs['min'] = str(today)

    def _validate_open_weekday(self, date, field_label):
        if date and date.weekday() not in self.allowed_weekdays:
            allowed_labels = ', '.join(WEEKDAY_LABELS[idx] for idx in sorted(self.allowed_weekdays))
            raise forms.ValidationError(
                f'{field_label} trebuie sa fie intr-o zi in care service-ul lucreaza. Programul curent acopera: {allowed_labels}.'
            )

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
            cleaned['car_vin'] = saved_car.vin

        if self.center and garage and garage.center_id != self.center.id:
            self.add_error('garage', 'Garajul selectat nu apartine acestui service.')

        requested_duration = normalize_duration_minutes(cleaned.get('duration_minutes') or 60)

        if garage and booking_date and booking_time and not garage.is_time_available(
            booking_date, booking_time, duration_minutes=requested_duration, booking_status=Booking.STATUS_PENDING
        ):
            self.add_error('booking_time', 'Prima preferinta nu mai este disponibila pentru garajul selectat.')

        if bool(cleaned.get('preferred_date_2')) != bool(cleaned.get('preferred_time_2')):
            self.add_error('preferred_time_2', 'Completeaza si ora pentru a doua preferinta.')
        if bool(cleaned.get('preferred_date_3')) != bool(cleaned.get('preferred_time_3')):
            self.add_error('preferred_time_3', 'Completeaza si ora pentru a treia preferinta.')

        attachments = cleaned.get('attachments') or []
        for uploaded in attachments:
            if not uploaded:
                continue
            try:
                validate_booking_media_file(uploaded)
            except forms.ValidationError as exc:
                self.add_error('attachments', exc)

        return cleaned

    def clean_booking_date(self):
        date = self.cleaned_data.get('booking_date')
        if date and date < timezone.now().date():
            raise forms.ValidationError('Prima preferinta nu poate fi in trecut.')
        self._validate_open_weekday(date, 'Prima preferinta')
        return date

    def clean_preferred_date_2(self):
        date = self.cleaned_data.get('preferred_date_2')
        if date and date < timezone.now().date():
            raise forms.ValidationError('A doua preferinta nu poate fi in trecut.')
        self._validate_open_weekday(date, 'A doua preferinta')
        return date

    def clean_preferred_date_3(self):
        date = self.cleaned_data.get('preferred_date_3')
        if date and date < timezone.now().date():
            raise forms.ValidationError('A treia preferinta nu poate fi in trecut.')
        self._validate_open_weekday(date, 'A treia preferinta')
        return date

    def clean_car_year(self):
        year = self.cleaned_data.get('car_year')
        current_year = timezone.now().year
        if year and (year < 1950 or year > current_year + 1):
            raise forms.ValidationError(f'Anul masinii trebuie sa fie intre 1950 si {current_year + 1}.')
        return year

    def clean_car_plate(self):
        plate = (self.cleaned_data.get('car_plate') or '').upper().strip()
        if not plate:
            raise forms.ValidationError('Introduceti numarul de inmatriculare.')
        return plate

    def clean_car_vin(self):
        vin = (self.cleaned_data.get('car_vin') or '').upper().strip()
        vin = ''.join(ch for ch in vin if ch.isalnum())
        if not vin:
            raise forms.ValidationError('VIN-ul este obligatoriu.')
        if len(vin) != 17:
            raise forms.ValidationError('VIN-ul trebuie sa aiba exact 17 caractere.')
        if any(ch in {'I', 'O', 'Q'} for ch in vin):
            raise forms.ValidationError('VIN-ul nu poate contine literele I, O sau Q.')
        return vin
