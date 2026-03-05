from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import ServiceCenter


class ServiceCenterRegisterForm(forms.ModelForm):
    """Form standard (din cont) pentru înregistrarea unui service."""

    class Meta:
        model = ServiceCenter
        fields = [
            'name',
            'category',
            'description',
            'address',
            'city',
            'phone',
            'email',
            'website',
            'schedule',
            # date legale (opțional)
            'legal_name',
            'headquarters',
            'fiscal_code',
            'trade_register_no',
            'legal_document',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Service Auto X'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'schedule': forms.TextInput(attrs={'class': 'form-control'}),

            'legal_name': forms.TextInput(attrs={'class': 'form-control'}),
            'headquarters': forms.TextInput(attrs={'class': 'form-control'}),
            'fiscal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'trade_register_no': forms.TextInput(attrs={'class': 'form-control'}),
            'legal_document': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def _any_legal_data(self, cleaned):
        return any([
            (cleaned.get('legal_name') or '').strip(),
            (cleaned.get('headquarters') or '').strip(),
            (cleaned.get('fiscal_code') or '').strip(),
            (cleaned.get('trade_register_no') or '').strip(),
        ])

    def clean(self):
        cleaned = super().clean()
        any_legal = self._any_legal_data(cleaned)
        doc = cleaned.get('legal_document')
        if any_legal and not doc:
            self.add_error(
                'legal_document',
                'Dacă ai completat datele legale, încarcă și un document care să ateste deținerea firmei.'
            )
        return cleaned

    def save(self, commit=True):
        center = super().save(commit=False)

        any_legal = self._any_legal_data(self.cleaned_data)
        if any_legal:
            # intră la verificare manuală
            center.verification_status = 'pending'
            center.is_active = False
        else:
            center.verification_status = 'not_required'
            center.is_active = True

        if commit:
            center.save()
            self.save_m2m()
        return center


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
        # Creează user
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

        center = super().save(commit=False)
        center.owner = user
        # ServiceCenterRegisterForm.save() setează status + is_active
        any_legal = self._any_legal_data(self.cleaned_data)
        if any_legal:
            center.verification_status = 'pending'
            center.is_active = False
        else:
            center.verification_status = 'not_required'
            center.is_active = True

        if commit:
            center.save()
            self.save_m2m()

        return center, user
