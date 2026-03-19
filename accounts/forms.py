from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

from .models import Car, CarExpiryProfile


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=50, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prenume'})
    )
    last_name = forms.CharField(
        max_length=50, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nume'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    accept_terms = forms.BooleanField(
        required=True,
        label='Accept documentele legale',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password1', 'password2', 'accept_terms']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nume utilizator'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Parolă'}
        )
        self.fields['password2'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Confirmă parola'}
        )

    def clean_accept_terms(self):
        accepted = self.cleaned_data.get('accept_terms')
        if not accepted:
            raise forms.ValidationError(
                f'Trebuie să accepți Termenii și condițiile, Politica de confidențialitate și Politica cookie (versiunea {settings.LEGAL_DOCUMENTS_VERSION}).'
            )
        return accepted

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Există deja un cont cu acest email.')
        return email


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget = forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'Nume utilizator'}
        )
        self.fields['password'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Parolă'}
        )


class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = ['make', 'model', 'year', 'fuel', 'plate_number', 'vin']
        widgets = {
            'make': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: Dacia, Volkswagen'}),
            'model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: Logan, Golf'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 1950, 'placeholder': 'ex: 2018'}),
            'fuel': forms.Select(
                attrs={'class': 'form-select'},
                choices=[
                    ('', '— Alege (opțional) —'),
                    ('benzina', 'Benzină'),
                    ('motorina', 'Motorină'),
                    ('hibrid', 'Hibrid'),
                    ('electric', 'Electric'),
                    ('gpl', 'GPL'),
                ],
            ),
            'plate_number': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'ex: B 123 ABC', 'style': 'text-transform:uppercase'}
            ),
            'vin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: UU1KSD0F554433221', 'style': 'text-transform:uppercase'}),
        }

    def clean_plate_number(self):
        plate = (self.cleaned_data.get('plate_number') or '').upper().strip()
        return plate


    def clean_vin(self):
        vin = (self.cleaned_data.get('vin') or '').upper().strip()
        vin = ''.join(ch for ch in vin if ch.isalnum())
        if not vin:
            raise forms.ValidationError('VIN-ul este obligatoriu.')
        if len(vin) != 17:
            raise forms.ValidationError('VIN-ul trebuie să aibă exact 17 caractere.')
        invalid = set('IOQ')
        if any(ch in invalid for ch in vin):
            raise forms.ValidationError('VIN-ul nu poate conține literele I, O sau Q.')
        return vin


class CarExpiryProfileForm(forms.ModelForm):
    class Meta:
        model = CarExpiryProfile
        fields = ['itp_expiry', 'rca_expiry', 'rovinieta_expiry', 'casco_expiry', 'trusa_expiry', 'extinctor_expiry']
        widgets = {
            'itp_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'rca_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'rovinieta_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'casco_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'trusa_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'extinctor_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
