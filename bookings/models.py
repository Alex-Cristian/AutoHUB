from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from services.models import ServiceCenter, ServiceGarage, ServiceItem


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_QUOTED = 'quoted'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_WAITING_PARTS = 'waiting_parts'
    STATUS_DONE = 'done'
    STATUS_CANCELLED = 'cancelled'

    TAG_URGENT = 'urgent'
    TAG_WAITING_PART = 'waiting_part'
    TAG_LOYAL_CLIENT = 'loyal_client'
    TAG_WARRANTY = 'warranty'
    TAG_PRIORITY = 'priority'
    TAG_BLOCKED = 'blocked'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'În așteptare'),
        (STATUS_QUOTED, 'Ofertă trimisă'),
        (STATUS_CONFIRMED, 'Confirmată'),
        (STATUS_IN_PROGRESS, 'În lucru'),
        (STATUS_WAITING_PARTS, 'Așteaptă piese'),
        (STATUS_DONE, 'Finalizată'),
        (STATUS_CANCELLED, 'Anulată'),
    ]
    TAG_CHOICES = [
        (TAG_URGENT, 'Urgent'),
        (TAG_WAITING_PART, 'Asteapta piesa'),
        (TAG_LOYAL_CLIENT, 'Client fidel'),
        (TAG_WARRANTY, 'Garantie'),
        (TAG_PRIORITY, 'Prioritar'),
        (TAG_BLOCKED, 'Blocat'),
    ]
    FUEL_CHOICES = [
        ('benzina', 'Benzina'),
        ('motorina', 'Motorina'),
        ('hibrid', 'Hibrid'),
        ('electric', 'Electric'),
        ('gpl', 'GPL'),
    ]
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Cerere trimisa'),
        (STATUS_QUOTED, 'Propunere trimisa'),
        (STATUS_CONFIRMED, 'Confirmata'),
        (STATUS_IN_PROGRESS, 'In lucru'),
        (STATUS_WAITING_PARTS, 'Asteapta aprobare client'),
        (STATUS_DONE, 'Finalizata'),
        (STATUS_CANCELLED, 'Respinsa'),
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
    mechanic = models.ForeignKey(
        'services.ServiceMechanic', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bookings', verbose_name='Mecanic alocat'
    )

    client_name = models.CharField(max_length=200, verbose_name='Nume complet')
    client_phone = models.CharField(max_length=20, verbose_name='Telefon')
    client_email = models.EmailField(verbose_name='Email')

    car_brand = models.CharField(max_length=100, verbose_name='Marca')
    car_model = models.CharField(max_length=100, verbose_name='Model')
    car_year = models.PositiveIntegerField(verbose_name='An fabricatie')
    car_fuel = models.CharField(
        max_length=20, choices=FUEL_CHOICES, verbose_name='Combustibil'
    )
    car_plate = models.CharField(max_length=20, verbose_name='Nr. inmatriculare')
    car_vin = models.CharField(max_length=17, default='', verbose_name='Serie sasiu (VIN)')

    problem_description = models.TextField(
        verbose_name='Descriere problema / serviciu dorit'
    )

    booking_date = models.DateField(verbose_name='Prima preferinta - data')
    booking_time = models.TimeField(verbose_name='Prima preferinta - ora')
    preferred_date_2 = models.DateField(null=True, blank=True, verbose_name='A doua preferinta - data')
    preferred_time_2 = models.TimeField(null=True, blank=True, verbose_name='A doua preferinta - ora')
    preferred_date_3 = models.DateField(null=True, blank=True, verbose_name='A treia preferinta - data')
    preferred_time_3 = models.TimeField(null=True, blank=True, verbose_name='A treia preferinta - ora')
    duration_minutes = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Durata estimata (minute)'
    )
    estimated_operation_slug = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Operatie estimata (slug)'
    )
    estimated_operation_label = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Operatie estimata'
    )
    duration_estimate_source = models.CharField(
        max_length=24, blank=True, default='', verbose_name='Sursa estimarii duratei'
    )
    duration_estimate_confidence = models.FloatField(
        null=True, blank=True, verbose_name='Incredere estimare durata'
    )
    estimated_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Pret aproximativ (RON)'
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_PENDING, verbose_name='Status'
    )
    notes = models.TextField(blank=True, verbose_name='Note interne')
    used_services = models.TextField(blank=True, verbose_name='Servicii / piese folosite')
    additional_description = models.TextField(blank=True, verbose_name='Descriere suplimentara pentru fisa')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reminder_sent_1d = models.BooleanField(default=False, verbose_name='Reminder SMS trimis cu o zi inainte')
    wants_offer = models.BooleanField(default=False, verbose_name='Client doreste oferta inainte de confirmare')
    needs_client_reschedule = models.BooleanField(default=False, verbose_name='Clientul trebuie sa aleaga un nou interval')
    operational_tags = models.JSONField(default=list, blank=True, verbose_name='Tag-uri operationale')

    class Meta:
        verbose_name = 'Cerere service'
        verbose_name_plural = 'Cereri service'
        ordering = ['-created_at']

    def __str__(self):
        garage_label = f" / {self.garage.name}" if self.garage_id else ''
        return (
            f"#{self.pk} {self.client_name} - "
            f"{self.car_brand} {self.car_model} "
            f"@ {self.center.name}{garage_label} [{self.booking_date}]"
        )

    def effective_duration_minutes(self):
        if self.duration_minutes:
            return self.duration_minutes
        if self.service_item_id and getattr(self.service_item, 'duration_minutes', None):
            return self.service_item.duration_minutes
        if self.garage_id and getattr(self.garage, 'slot_minutes', None):
            return self.garage.slot_minutes
        return 60

    @property
    def is_request_phase(self):
        return self.status in {self.STATUS_PENDING, self.STATUS_QUOTED, self.STATUS_CONFIRMED}

    @property
    def is_work_phase(self):
        return self.status in {self.STATUS_IN_PROGRESS, self.STATUS_WAITING_PARTS, self.STATUS_DONE}

    @property
    def request_status_label(self):
        labels = {
            self.STATUS_PENDING: 'In analiza',
            self.STATUS_QUOTED: 'Reprogramare / oferta propusa',
            self.STATUS_CONFIRMED: 'Confirmata',
            self.STATUS_IN_PROGRESS: 'Confirmata',
            self.STATUS_WAITING_PARTS: 'Confirmata',
            self.STATUS_DONE: 'Confirmata',
            self.STATUS_CANCELLED: 'Respinsa',
        }
        return labels.get(self.status, self.get_status_display())

    @property
    def work_status_label(self):
        labels = {
            self.STATUS_PENDING: 'Nu a inceput',
            self.STATUS_QUOTED: 'Asteapta acceptul clientului',
            self.STATUS_CONFIRMED: 'In asteptarea receptiei',
            self.STATUS_IN_PROGRESS: 'In lucru',
            self.STATUS_WAITING_PARTS: 'Asteapta aprobare client',
            self.STATUS_DONE: 'Finalizat',
            self.STATUS_CANCELLED: 'Nu s-a deschis',
        }
        return labels.get(self.status, self.get_status_display())

    def preferred_slots(self):
        slots = []
        for date_value, time_value in (
            (self.booking_date, self.booking_time),
            (self.preferred_date_2, self.preferred_time_2),
            (self.preferred_date_3, self.preferred_time_3),
        ):
            if date_value and time_value:
                slots.append({
                    'date': date_value,
                    'time': time_value,
                    'label': f"{date_value.strftime('%d.%m.%Y')} · {time_value.strftime('%H:%M')}",
                })
        return slots

    def get_start_datetime(self):
        if not self.booking_date or not self.booking_time:
            return None
        return datetime.combine(self.booking_date, self.booking_time)

    def get_end_datetime(self):
        start = self.get_start_datetime()
        if not start:
            return None
        return start + timedelta(minutes=self.effective_duration_minutes())

    def clean(self):
        if self.booking_date and self.booking_date < timezone.localdate():
            raise ValidationError({
                'booking_date': 'Prima preferinta nu poate fi in trecut.'
            })
        for field_name in ('preferred_date_2', 'preferred_date_3'):
            preferred_date = getattr(self, field_name)
            if preferred_date and preferred_date < timezone.localdate():
                raise ValidationError({
                    field_name: 'Preferinta nu poate fi in trecut.'
                })
        current_year = timezone.now().year
        if self.car_year and (self.car_year < 1950 or self.car_year > current_year + 1):
            raise ValidationError({
                'car_year': f'Anul masinii trebuie sa fie intre 1950 si {current_year + 1}.'
            })

        vin = ''.join(ch for ch in (self.car_vin or '').upper().strip() if ch.isalnum())
        self.car_vin = vin
        if not vin:
            raise ValidationError({'car_vin': 'VIN-ul este obligatoriu.'})
        if len(vin) != 17:
            raise ValidationError({'car_vin': 'VIN-ul trebuie sa aiba exact 17 caractere.'})
        if any(ch in {'I', 'O', 'Q'} for ch in vin):
            raise ValidationError({'car_vin': 'VIN-ul nu poate contine literele I, O sau Q.'})

        duration = self.effective_duration_minutes()
        if duration < 30 or duration > 12 * 60:
            raise ValidationError({'duration_minutes': 'Durata trebuie sa fie intre 30 minute si 12 ore.'})

        if self.garage_id and self.center_id and self.garage.center_id != self.center_id:
            raise ValidationError({'garage': 'Garajul selectat nu apartine service-ului ales.'})
        if self.mechanic_id and self.center_id and self.mechanic.center_id != self.center_id:
            raise ValidationError({'mechanic': 'Mecanicul selectat nu apartine service-ului ales.'})

        if self.garage_id and self.booking_date and self.booking_time:
            start_dt = datetime.combine(self.booking_date, self.booking_time)
            end_dt = start_dt + timedelta(minutes=duration)
            garage_open = datetime.combine(self.booking_date, self.garage.open_time)
            garage_close = datetime.combine(self.booking_date, self.garage.close_time)
            if start_dt < garage_open or end_dt > garage_close:
                raise ValidationError({'booking_time': 'Preferinta aleasa trebuie sa fie in intervalul de lucru al garajului.'})
            if not self.garage.is_time_available(
                self.booking_date,
                self.booking_time,
                duration_minutes=duration,
                exclude_booking_id=self.pk,
                booking_status=self.status,
            ):
                raise ValidationError({'booking_time': 'Prima preferinta nu mai este disponibila pentru garajul selectat.'})

        if self.mechanic_id and self.booking_date and self.booking_time:
            if not self.mechanic.is_time_available(
                self.booking_date,
                self.booking_time,
                duration_minutes=duration,
                exclude_booking_id=self.pk,
            ):
                raise ValidationError({'mechanic': 'Mecanicul selectat este deja alocat in acest interval.'})

        allowed_tags = {choice[0] for choice in self.TAG_CHOICES}
        selected_tags = self.operational_tags or []
        invalid_tags = [tag for tag in selected_tags if tag not in allowed_tags]
        if invalid_tags:
            raise ValidationError({'operational_tags': 'Unul sau mai multe tag-uri operationale nu sunt valide.'})

    def get_duration_display(self):
        minutes = self.effective_duration_minutes()
        hours, mins = divmod(minutes, 60)
        if hours and mins:
            return f"{hours}:{mins:02d}"
        if hours:
            return '1 ora' if hours == 1 else f"{hours} ore"
        return f"{mins} min"

    def get_status_badge(self):
        classes = {
            self.STATUS_PENDING: 'warning text-dark',
            self.STATUS_QUOTED: 'secondary',
            self.STATUS_CONFIRMED: 'info text-dark',
            self.STATUS_IN_PROGRESS: 'primary',
            self.STATUS_WAITING_PARTS: 'warning text-dark',
            self.STATUS_DONE: 'success',
            self.STATUS_CANCELLED: 'danger',
        }
        return classes.get(self.status, 'secondary')

    def get_status_icon(self):
        icons = {
            self.STATUS_PENDING: '⏳',
            self.STATUS_QUOTED: '💬',
            self.STATUS_CONFIRMED: '✅',
            self.STATUS_IN_PROGRESS: '🔧',
            self.STATUS_WAITING_PARTS: '🧰',
            self.STATUS_DONE: '🏁',
            self.STATUS_CANCELLED: '❌',
        }
        return icons.get(self.status, '❔')

    def has_operational_tag(self, tag):
        return tag in (self.operational_tags or [])

    def operational_tag_labels(self):
        labels = dict(self.TAG_CHOICES)
        return [labels[tag] for tag in (self.operational_tags or []) if tag in labels]

    def needs_attention(self):
        active_statuses = {
            self.STATUS_PENDING,
            self.STATUS_QUOTED,
            self.STATUS_CONFIRMED,
            self.STATUS_IN_PROGRESS,
            self.STATUS_WAITING_PARTS,
        }
        if self.status not in active_statuses:
            return False
        if self.status in {self.STATUS_CONFIRMED, self.STATUS_IN_PROGRESS, self.STATUS_WAITING_PARTS} and not self.garage_id:
            return True
        if self.status in {self.STATUS_IN_PROGRESS, self.STATUS_WAITING_PARTS} and not self.mechanic_id:
            return True
        return self.has_operational_tag(self.TAG_BLOCKED) or self.has_operational_tag(self.TAG_WAITING_PART)


class BookingAttachment(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='booking_attachments/')
    media_kind = models.CharField(max_length=10, choices=[('image', 'Imagine'), ('video', 'Video')])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Atasament cerere/lucrare'
        verbose_name_plural = 'Atasamente cereri/lucrari'
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
        (KIND_BOOKING_NEW, 'Cerere noua'),
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
        verbose_name = 'Notificare cerere'
        verbose_name_plural = 'Notificari cereri'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.username}: {self.title}"


class BookingActivityLog(models.Model):
    EVENT_STATUS_CHANGED = 'status_changed'
    EVENT_OFFER_UPDATED = 'offer_updated'
    EVENT_MECHANIC_CHANGED = 'mechanic_changed'
    EVENT_SCHEDULE_CHANGED = 'schedule_changed'
    EVENT_ATTACHMENT_ADDED = 'attachment_added'
    EVENT_NOTE_UPDATED = 'note_updated'
    EVENT_TAGS_UPDATED = 'tags_updated'
    EVENT_CHECKLIST_UPDATED = 'checklist_updated'

    EVENT_CHOICES = [
        (EVENT_STATUS_CHANGED, 'Status schimbat'),
        (EVENT_OFFER_UPDATED, 'Oferta actualizata'),
        (EVENT_MECHANIC_CHANGED, 'Mecanic schimbat'),
        (EVENT_SCHEDULE_CHANGED, 'Programare mutata'),
        (EVENT_ATTACHMENT_ADDED, 'Fisier adaugat'),
        (EVENT_NOTE_UPDATED, 'Nota interna actualizata'),
        (EVENT_TAGS_UPDATED, 'Tag-uri actualizate'),
        (EVENT_CHECKLIST_UPDATED, 'Checklist actualizat'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='activity_logs')
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='booking_activity_logs')
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    message = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Activity log booking'
        verbose_name_plural = 'Activity logs booking'

    def __str__(self):
        return f"#{self.booking_id} {self.event_type}"


class BookingChecklistItem(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='checklist_items')
    label = models.CharField(max_length=160)
    is_done = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_booking_checklist_items')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at', 'pk']
        verbose_name = 'Checklist booking'
        verbose_name_plural = 'Checklist booking'

    def __str__(self):
        return f"#{self.booking_id} {self.label}"
