from datetime import datetime, timedelta

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from services.models import ServiceCenter, ServiceItem, ServiceGarage


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'În așteptare'),
        (STATUS_CONFIRMED, 'Confirmată'),
        (STATUS_IN_PROGRESS, 'În lucru'),
        (STATUS_DONE, 'Finalizată'),
        (STATUS_CANCELLED, 'Anulată'),
    ]

    FUEL_CHOICES = [
        ('benzina', 'Benzină'),
        ('motorina', 'Motorină'),
        ('hibrid', 'Hibrid'),
        ('electric', 'Electric'),
        ('gpl', 'GPL'),
    ]

    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bookings', verbose_name='Cont utilizator'
    )
    center = models.ForeignKey(
        ServiceCenter, on_delete=models.CASCADE,
        related_name='bookings', verbose_name='Service'
    )
    garage = models.ForeignKey(
        ServiceGarage, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bookings', verbose_name='Garaj'
    )
    service_item = models.ForeignKey(
        ServiceItem, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name='Serviciu ales'
    )

    client_name = models.CharField(max_length=200, verbose_name='Nume complet')
    client_phone = models.CharField(max_length=20, verbose_name='Telefon')
    client_email = models.EmailField(verbose_name='Email')

    car_brand = models.CharField(max_length=100, verbose_name='Marcă')
    car_model = models.CharField(max_length=100, verbose_name='Model')
    car_year = models.PositiveIntegerField(verbose_name='An fabricație')
    car_fuel = models.CharField(
        max_length=20, choices=FUEL_CHOICES, verbose_name='Combustibil'
    )
    car_plate = models.CharField(max_length=20, verbose_name='Nr. înmatriculare')

    problem_description = models.TextField(
        verbose_name='Descriere problemă / serviciu dorit'
    )

    booking_date = models.DateField(verbose_name='Data programării')
    booking_time = models.TimeField(verbose_name='Ora programării')

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_PENDING, verbose_name='Status'
    )
    notes = models.TextField(blank=True, verbose_name='Note interne (admin)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Programare'
        verbose_name_plural = 'Programări'
        ordering = ['-created_at']

    def __str__(self):
        garage_label = f" / {self.garage.name}" if self.garage_id else ''
        return (
            f"#{self.pk} {self.client_name} – "
            f"{self.car_brand} {self.car_model} "
            f"@ {self.center.name}{garage_label} [{self.booking_date}]"
        )

    def clean(self):
        if self.booking_date and self.booking_date < timezone.now().date():
            raise ValidationError({
                'booking_date': 'Data programării nu poate fi în trecut.'
            })
        current_year = timezone.now().year
        if self.car_year and (self.car_year < 1950 or self.car_year > current_year + 1):
            raise ValidationError({
                'car_year': f'Anul mașinii trebuie să fie între 1950 și {current_year + 1}.'
            })
        if self.garage_id and self.center_id and self.garage.center_id != self.center_id:
            raise ValidationError({'garage': 'Garajul selectat nu aparține service-ului ales.'})
        if self.garage_id and self.booking_date and self.booking_time:
            if not self.garage.is_time_available(self.booking_date, self.booking_time, exclude_booking_id=self.pk):
                raise ValidationError({'booking_time': 'Intervalul ales nu mai este disponibil pentru garajul selectat.'})

    def get_status_badge(self):
        classes = {
            'pending': 'warning text-dark',
            'confirmed': 'info text-dark',
            'in_progress': 'primary',
            'done': 'success',
            'cancelled': 'danger',
        }
        return classes.get(self.status, 'secondary')

    def get_status_icon(self):
        icons = {
            'pending': '⏳',
            'confirmed': '✅',
            'in_progress': '🔧',
            'done': '🏁',
            'cancelled': '❌',
        }
        return icons.get(self.status, '❓')


class BookingAttachment(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='booking_attachments/')
    media_kind = models.CharField(max_length=10, choices=[('image', 'Imagine'), ('video', 'Video')])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Atașament programare'
        verbose_name_plural = 'Atașamente programări'
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.media_kind} #{self.pk} pentru programarea {self.booking_id}"

    @property
    def is_image(self):
        return self.media_kind == 'image'

    @property
    def is_video(self):
        return self.media_kind == 'video'


class BookingNotification(models.Model):
    KIND_BOOKING_NEW = 'booking_new'
    KIND_STATUS_UPDATE = 'status_update'

    KIND_CHOICES = [
        (KIND_BOOKING_NEW, 'Programare nouă'),
        (KIND_STATUS_UPDATE, 'Actualizare status'),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='booking_notifications'
    )
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='notifications'
    )
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notificare programare'
        verbose_name_plural = 'Notificări programări'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.username}: {self.title}"
