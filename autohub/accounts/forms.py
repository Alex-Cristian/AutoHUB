from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

from .models import Car, CarExpiryCalendar


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

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password1', 'password2']
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
            'vin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'opțional'}),
        }

    def clean_plate_number(self):
        plate = (self.cleaned_data.get('plate_number') or '').upper().strip()
        return plate



class CarExpiryCalendarForm(forms.ModelForm):
    class Meta:
        model = CarExpiryCalendar
        fields = ['itp_expiry', 'rca_expiry', 'rovinieta_expiry', 'trusa_expiry', 'extinctor_expiry']
        widgets = {
            'itp_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'rca_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'rovinieta_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'trusa_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'extinctor_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'itp_expiry': 'ITP',
            'rca_expiry': 'RCA',
            'rovinieta_expiry': 'Rovinietă',
            'trusa_expiry': 'Trusă auto',
            'extinctor_expiry': 'Extinctor',
        }
        help_texts = {
            'itp_expiry': 'Lasă gol dacă nu vrei să o setezi acum.',
        }
