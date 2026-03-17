from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse
from django.db.models import Avg
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError


CITY_CHOICES = [
    ('bucuresti', 'București'),
    ('cluj-napoca', 'Cluj-Napoca'),
    ('timisoara', 'Timișoara'),
    ('iasi', 'Iași'),
    ('brasov', 'Brașov'),
    ('constanta', 'Constanța'),
    ('craiova', 'Craiova'),
    ('galati', 'Galați'),
    ('ploiesti', 'Ploiești'),
    ('oradea', 'Oradea'),
    ('sibiu', 'Sibiu'),
    ('arad', 'Arad'),
    ('pitesti', 'Pitești'),
    ('bacau', 'Bacău'),
    ('targu-mures', 'Târgu Mureș'),
]


class ServiceCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name='Denumire')
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, verbose_name='Descriere')
    icon = models.CharField(max_length=50, default='🔧', verbose_name='Icon (emoji)')
    color = models.CharField(max_length=20, default='#e63946', verbose_name='Culoare hex')
    order = models.PositiveIntegerField(default=0, verbose_name='Ordine afișare')

    class Meta:
        verbose_name = 'Categorie Serviciu'
        verbose_name_plural = 'Categorii Servicii'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('services:list') + f'?category={self.slug}'

    def center_count(self):
        from django.db.models import Q
        return ServiceCenter.objects.filter(
            Q(category=self) | Q(categories=self),
            is_active=True
        ).distinct().count()


class ServiceCenter(models.Model):
    name = models.CharField(max_length=200, verbose_name='Denumire service')
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(
        ServiceCategory, on_delete=models.CASCADE, verbose_name='Categorie principală'
    )
    categories = models.ManyToManyField(
        ServiceCategory,
        blank=True,
        related_name='center_categories',
        verbose_name='Categorii disponibile'
    )
    description = models.TextField(verbose_name='Descriere')
    address = models.CharField(max_length=300, verbose_name='Adresă')
    city = models.CharField(max_length=50, choices=CITY_CHOICES, verbose_name='Oraș')
    phone = models.CharField(max_length=20, verbose_name='Telefon')
    email = models.EmailField(blank=True, verbose_name='Email')
    website = models.URLField(blank=True, verbose_name='Website')
    schedule = models.CharField(
        max_length=200, default='Lun-Vin: 08:00-18:00',
        verbose_name='Program lucru'
    )
    latitude = models.DecimalField(max_digits=11, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=7, null=True, blank=True)
    card_image = models.ImageField(
        upload_to='service_cards/', blank=True, null=True,
        verbose_name='Poză card service'
    )

    legal_name = models.CharField(max_length=255, blank=True, verbose_name='Denumire legală (opțional)')
    headquarters = models.CharField(max_length=300, blank=True, verbose_name='Sediu social (opțional)')
    fiscal_code = models.CharField(max_length=50, blank=True, verbose_name='Cod fiscal / CIF (opțional)')
    trade_register_no = models.CharField(max_length=50, blank=True, verbose_name='Nr. Registrul Comerțului (opțional)')
    legal_document = models.FileField(
        upload_to='legal_docs/', blank=True, null=True,
        verbose_name='Document legal (opțional)'
    )

    VERIFICATION_CHOICES = [
        ('not_required', 'Nu necesită verificare'),
        ('pending', 'În așteptare verificare'),
        ('verified', 'Verificat'),
        ('rejected', 'Respins'),
    ]
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_CHOICES, default='not_required',
        verbose_name='Status verificare'
    )
    verification_note = models.TextField(blank=True, verbose_name='Notă verificare (intern)')
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Verificat la')

    is_active = models.BooleanField(default=True, verbose_name='Activ')
    is_featured = models.BooleanField(default=False, verbose_name='Recomandat')
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='owned_centers', verbose_name='Proprietar cont'
    )

    class Meta:
        verbose_name = 'Service Auto'
        verbose_name_plural = 'Service-uri Auto'
        ordering = ['-is_featured', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_city_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            n = 1
            while ServiceCenter.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('services:detail', kwargs={'slug': self.slug})

    def avg_rating(self):
        result = self.review_set.filter(is_approved=True).aggregate(avg=Avg('rating'))
        val = result['avg']
        return round(val, 1) if val else 0.0

    def review_count(self):
        return self.review_set.filter(is_approved=True).count()

    def min_price(self):
        from django.db.models import Min
        return self.serviceitem_set.aggregate(m=Min('price_from'))['m']

    def max_price(self):
        from django.db.models import Max
        return self.serviceitem_set.aggregate(m=Max('price_to'))['m']

    def is_favorited_by(self, user):
        if user and user.is_authenticated:
            return self.favorites.filter(user=user).exists()
        return False

    def display_categories(self):
        categories = list(self.categories.all())
        if categories:
            return categories
        return [self.category] if self.category_id else []


class ServiceGarage(models.Model):
    center = models.ForeignKey(ServiceCenter, on_delete=models.CASCADE, related_name='garages', verbose_name='Service')
    name = models.CharField(max_length=120, verbose_name='Nume garaj')
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, verbose_name='Categorie')
    open_time = models.TimeField(default='08:00', verbose_name='Deschidere')
    close_time = models.TimeField(default='18:00', verbose_name='Închidere')
    slot_minutes = models.PositiveIntegerField(default=60, verbose_name='Durată slot (minute)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Garaj service'
        verbose_name_plural = 'Garaje service'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.center.name}"

    def clean(self):

        if not self.center_id:
            return

        allowed_ids = set(self.center.categories.values_list('id', flat=True))
        if not allowed_ids and self.center.category_id:
            allowed_ids.add(self.center.category_id)

        if self.category_id and self.category_id not in allowed_ids:
            raise ValidationError({'category': 'Poți alege doar o categorie din cele selectate de service.'})

        if self.close_time <= self.open_time:
            raise ValidationError({'close_time': 'Ora de închidere trebuie să fie după ora de deschidere.'})

    def available_slots_for_date(self, booking_date, duration_minutes=None):
        if not booking_date:
            return []
        requested_duration = max(duration_minutes or 30, 30)
        slots = []
        start_dt = datetime.combine(booking_date, self.open_time)
        end_dt = datetime.combine(booking_date, self.close_time)
        step = timedelta(minutes=30)
        current = start_dt
        while current + timedelta(minutes=requested_duration) <= end_dt:
            slot_time = current.time().replace(second=0, microsecond=0)
            if self.is_time_available(booking_date, slot_time, duration_minutes=requested_duration):
                slots.append(slot_time.strftime('%H:%M'))
            current += step
        return slots

    def is_time_available(self, booking_date, booking_time, duration_minutes=None, exclude_booking_id=None, booking_status=None):
        requested_duration = max(duration_minutes or 60, 30)
        requested_start = datetime.combine(booking_date, booking_time)
        requested_end = requested_start + timedelta(minutes=requested_duration)

        blocked_statuses = ['confirmed', 'in_progress']
        qs = self.bookings.filter(booking_date=booking_date, status__in=blocked_statuses)
        if exclude_booking_id:
            qs = qs.exclude(pk=exclude_booking_id)

        for booking in qs.select_related('service_item'):
            existing_start = datetime.combine(booking.booking_date, booking.booking_time)
            existing_duration = booking.duration_minutes or getattr(booking.service_item, 'duration_minutes', None) or self.slot_minutes or 60
            existing_end = existing_start + timedelta(minutes=max(existing_duration, 30))
            if requested_start < existing_end and requested_end > existing_start:
                return False
        return True




class ServiceMechanic(models.Model):
    center = models.ForeignKey(ServiceCenter, on_delete=models.CASCADE, related_name='mechanics', verbose_name='Service')
    name = models.CharField(max_length=160, verbose_name='Nume mecanic')
    email = models.EmailField(blank=True, verbose_name='Email')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Telefon')
    specialization = models.CharField(max_length=200, blank=True, verbose_name='Specializare')
    photo = models.ImageField(upload_to='mechanic_photos/', blank=True, null=True, verbose_name='Fotografie')
    garage = models.ForeignKey(
        'ServiceGarage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='mechanics', verbose_name='Garaj alocat'
    )
    service_categories = models.ManyToManyField(
        'ServiceCategory', blank=True,
        related_name='mechanics', verbose_name='Categorii servicii'
    )
    is_active = models.BooleanField(default=True, verbose_name='Activ')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mecanic service'
        verbose_name_plural = 'Mecanici service'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.center.name}"

    def active_bookings_count(self):
        return self.bookings.filter(status__in=['confirmed', 'in_progress']).count()

    def completed_bookings_count(self):
        return self.bookings.filter(status='done').count()


class MechanicWorkLog(models.Model):
    booking = models.OneToOneField(
        'bookings.Booking', on_delete=models.CASCADE,
        related_name='work_log', verbose_name='Programare'
    )
    mechanic = models.ForeignKey(
        ServiceMechanic, on_delete=models.CASCADE,
        related_name='work_logs', verbose_name='Mecanic'
    )
    repair_description = models.TextField(blank=True, verbose_name='Descriere reparatie')
    parts_used = models.TextField(blank=True, verbose_name='Piese folosite')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Inceput lucru')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='Terminat lucru')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fisa lucru mecanic'
        verbose_name_plural = 'Fise lucru mecanici'
        ordering = ['-created_at']

    def __str__(self):
        return f"Fisa #{self.pk} - {self.mechanic.name} / {self.booking}"


class MechanicPhoto(models.Model):
    PHOTO_TYPE_BEFORE = 'before'
    PHOTO_TYPE_AFTER = 'after'
    PHOTO_TYPE_DURING = 'during'
 
    PHOTO_TYPE_CHOICES = [
        (PHOTO_TYPE_BEFORE, 'Inainte de reparatie'),
        (PHOTO_TYPE_AFTER, 'Dupa reparatie'),
        (PHOTO_TYPE_DURING, 'In timpul reparatiei'),
    ]
    work_log = models.ForeignKey(
        MechanicWorkLog, on_delete=models.CASCADE,
        related_name='photos', verbose_name='Fisa lucru'
    )
    photo = models.ImageField(upload_to='mechanic_work_photos/', verbose_name='Fotografie')
    photo_type = models.CharField(
        max_length=10, choices=PHOTO_TYPE_CHOICES,
        default=PHOTO_TYPE_BEFORE, verbose_name='Tip fotografie'
    )
    caption = models.CharField(max_length=200, blank=True, verbose_name='Descriere')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Fotografie lucru'
        verbose_name_plural = 'Fotografii lucru'
        ordering = ['photo_type', 'uploaded_at']

    def __str__(self):
        return f"{self.get_photo_type_display()} - {self.work_log}"

class ServiceImage(models.Model):
    center = models.ForeignKey(ServiceCenter, on_delete=models.CASCADE, related_name='gallery_images', verbose_name='Service')
    image = models.ImageField(upload_to='service_gallery/', verbose_name='Poză')
    caption = models.CharField(max_length=120, blank=True, verbose_name='Descriere scurtă')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Poză service'
        verbose_name_plural = 'Poze service'
        ordering = ['-created_at']

    def __str__(self):
        return self.caption or f"Poză {self.pk} - {self.center.name}"


class ServiceItem(models.Model):
    center = models.ForeignKey(
        ServiceCenter, on_delete=models.CASCADE,
        related_name='serviceitem_set', verbose_name='Service'
    )
    name = models.CharField(max_length=200, verbose_name='Denumire serviciu')
    description = models.TextField(blank=True, verbose_name='Detalii')
    price_from = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Preț de la (RON)'
    )
    price_to = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Preț până la (RON)'
    )
    duration_minutes = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Durată estimată (min)'
    )
    is_popular = models.BooleanField(default=False, verbose_name='Popular')

    class Meta:
        verbose_name = 'Serviciu Oferit'
        verbose_name_plural = 'Servicii Oferite'
        ordering = ['-is_popular', 'name']

    def __str__(self):
        return f"{self.name} @ {self.center.name}"

    def price_display(self):
        if self.price_from and self.price_to:
            return f"{int(self.price_from)} – {int(self.price_to)} RON"
        elif self.price_from:
            return f"de la {int(self.price_from)} RON"
        return "La cerere"


class ServicePart(models.Model):
    center = models.ForeignKey(
        ServiceCenter, on_delete=models.CASCADE,
        related_name='parts', verbose_name='Service'
    )
    name = models.CharField(max_length=160, verbose_name='Denumire piesă')
    part_number = models.CharField(max_length=80, blank=True, verbose_name='Cod piesă')
    stock = models.PositiveIntegerField(default=0, verbose_name='Stoc curent')
    minimum_stock = models.PositiveIntegerField(default=0, verbose_name='Stoc minim')
    unit = models.CharField(max_length=20, default='buc', verbose_name='Unitate')
    shelf = models.CharField(max_length=80, blank=True, verbose_name='Raft / locație')
    notes = models.TextField(blank=True, verbose_name='Observații')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Piesă service'
        verbose_name_plural = 'Piese service'
        ordering = ['name']
        unique_together = ['center', 'name', 'part_number']

    def __str__(self):
        code = f" ({self.part_number})" if self.part_number else ''
        return f"{self.name}{code} - {self.center.name}"

    @property
    def is_low_stock(self):
        return self.stock <= self.minimum_stock


class Review(models.Model):
    RATING_CHOICES = [(i, f'{i} ★') for i in range(1, 6)]

    center = models.ForeignKey(
        ServiceCenter, on_delete=models.CASCADE, verbose_name='Service'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name='Utilizator'
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES, verbose_name='Rating'
    )
    title = models.CharField(max_length=200, verbose_name='Titlu recenzie')
    body = models.TextField(verbose_name='Textul recenziei')
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=True, verbose_name='Aprobată')

    class Meta:
        verbose_name = 'Recenzie'
        verbose_name_plural = 'Recenzii'
        ordering = ['-created_at']
        unique_together = ['center', 'user']

    def __str__(self):
        return f"{self.user.username} → {self.center.name} ({self.rating}★)"

    def clean(self):
        from bookings.models import Booking

        if self.user_id and self.center_id:
            has_done_booking = Booking.objects.filter(
                user_id=self.user_id,
                center_id=self.center_id,
                status=Booking.STATUS_DONE,
            ).exists()
            if not has_done_booking:
                raise ValidationError('Poți lăsa o recenzie doar după o programare finalizată la acest service.')

    def stars_range(self):
        return range(1, self.rating + 1)

    def empty_stars_range(self):
        return range(self.rating + 1, 6)


class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='review_images/', verbose_name='Poză recenzie')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Poză recenzie'
        verbose_name_plural = 'Poze recenzii'
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Poză recenzie {self.review_id}"


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    center = models.ForeignKey(
        ServiceCenter, on_delete=models.CASCADE, related_name='favorites'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'center']
        verbose_name = 'Favorit'
        verbose_name_plural = 'Favorite'

    def __str__(self):
        return f"{self.user.username} ♥ {self.center.name}"


class ServiceContract(models.Model):
    company_name = models.CharField(max_length=255, verbose_name='Nume companie / service')
    contact_person = models.CharField(max_length=120, blank=True, verbose_name='Persoană contact')
    contact_email = models.EmailField(blank=True, verbose_name='Email contact')
    contact_phone = models.CharField(max_length=30, blank=True, verbose_name='Telefon contact')
    notes = models.TextField(blank=True, verbose_name='Observații interne')
    is_signed = models.BooleanField(default=False, verbose_name='Contract semnat')
    signed_at = models.DateTimeField(null=True, blank=True, verbose_name='Semnat la')
    access_token = models.CharField(max_length=64, unique=True, blank=True, verbose_name='Token acces')
    access_token_created_at = models.DateTimeField(null=True, blank=True, verbose_name='Token generat la')
    access_link_used_at = models.DateTimeField(null=True, blank=True, verbose_name='Link folosit la')
    linked_owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='service_contracts', verbose_name='Proprietar cont legat')
    linked_center = models.ForeignKey(ServiceCenter, null=True, blank=True, on_delete=models.SET_NULL, related_name='contracts', verbose_name='Service creat')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_service_contracts', verbose_name='Creat de')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contract service'
        verbose_name_plural = 'Contracte service'
        ordering = ['-created_at']

    def __str__(self):
        return self.company_name