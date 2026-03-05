from django import forms

from .models import ServiceCenter


class ServiceCenterRegisterForm(forms.ModelForm):
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
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
