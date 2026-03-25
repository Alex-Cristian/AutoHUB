from django import forms
from django.forms import inlineformset_factory

from .models import Invoice, InvoiceLine


class InvoiceForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        issue_date = cleaned.get('issue_date')
        due_date = cleaned.get('due_date')
        if issue_date and due_date and due_date < issue_date:
            self.add_error('due_date', 'Scadenta nu poate fi inaintea datei emiterii.')
        return cleaned

    class Meta:
        model = Invoice
        fields = [
            'issue_date', 'due_date',
            'client_name', 'client_email', 'client_phone', 'client_address', 'client_fiscal_code',
            'notes',
        ]
        widgets = {
            'issue_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'due_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'client_name': forms.TextInput(attrs={'class': 'form-control', 'data-testid': 'invoice-client-name'}),
            'client_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'client_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'client_address': forms.TextInput(attrs={'class': 'form-control'}),
            'client_fiscal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class InvoiceLineForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Liniile extra trebuie sa porneasca goale; altfel formularul devine invalid
        # din cauza valorilor implicite ale modelului pe randurile necompletate.
        if not self.is_bound and not getattr(self.instance, "pk", None):
            self.initial.setdefault('quantity', '')
            self.initial.setdefault('unit_price', '')

    class Meta:
        model = InvoiceLine
        fields = ['description', 'quantity', 'unit_price']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Schimb ulei + filtru', 'data-testid': 'invoice-line-description'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'data-testid': 'invoice-line-quantity'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'data-testid': 'invoice-line-unit-price'}),
        }


InvoiceLineFormSet = inlineformset_factory(
    Invoice,
    InvoiceLine,
    form=InvoiceLineForm,
    extra=1,
    can_delete=True,
)
