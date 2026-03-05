from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse
from django.db.models import Avg, Count


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
        return self.servicecenter_set.filter(is_active=True).count()


class ServiceCenter(models.Model):
    name = models.CharField(max_length=200, verbose_name='Denumire service')
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(
        ServiceCategory, on_delete=models.CASCADE, verbose_name='Categorie principală'
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
    # Mock geo coords
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)


    # --- Date legale (opțional) ---
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
        result = self.serviceitem_set.aggregate(m=Min('price_from'))
        return result['m']

    def max_price(self):
        from django.db.models import Max
        result = self.serviceitem_set.aggregate(m=Max('price_to'))
        return result['m']

    def is_favorited_by(self, user):
        if user and user.is_authenticated:
            return self.favorites.filter(user=user).exists()
        return False


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

    def stars_range(self):
        return range(1, self.rating + 1)

    def empty_stars_range(self):
        return range(self.rating + 1, 6)


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