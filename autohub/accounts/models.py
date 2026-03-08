from django.conf import settings
from datetime import date

from django.db import models


class Car(models.Model):
    """Mașina salvată în contul utilizatorului."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cars',
        verbose_name='Utilizator',
    )

    make = models.CharField(max_length=50, verbose_name='Marcă')
    model = models.CharField(max_length=50, verbose_name='Model')
    year = models.PositiveIntegerField(null=True, blank=True, verbose_name='An fabricație')
    fuel = models.CharField(max_length=20, blank=True, verbose_name='Combustibil')
    plate_number = models.CharField(max_length=15, verbose_name='Nr. înmatriculare')
    vin = models.CharField(max_length=17, blank=True, verbose_name='Serie șasiu (VIN)')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mașină'
        verbose_name_plural = 'Mașini'
        unique_together = ('owner', 'plate_number')
        ordering = ['make', 'model', 'plate_number']

    def __str__(self):
        bits = [self.make, self.model]
        if self.year:
            bits.append(str(self.year))
        bits.append(f"({self.plate_number})")
        return " ".join(bits)


class CarExpiryCalendar(models.Model):
    """Calendar opțional cu datele de expirare pentru o mașină."""

    car = models.OneToOneField(
        Car,
        on_delete=models.CASCADE,
        related_name='expiry_calendar',
        verbose_name='Mașină',
    )

    itp_expiry = models.DateField(null=True, blank=True, verbose_name='Expirare ITP')
    rca_expiry = models.DateField(null=True, blank=True, verbose_name='Expirare RCA')
    rovinieta_expiry = models.DateField(null=True, blank=True, verbose_name='Expirare rovinietă')
    trusa_expiry = models.DateField(null=True, blank=True, verbose_name='Expirare trusă auto')
    extinctor_expiry = models.DateField(null=True, blank=True, verbose_name='Expirare extinctor')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Calendar expirări mașină'
        verbose_name_plural = 'Calendare expirări mașini'

    def __str__(self):
        return f"Calendar expirări — {self.car}"

    @staticmethod
    def _days_until(target_date):
        if not target_date:
            return None
        return (target_date - date.today()).days

    @classmethod
    def _status_for_date(cls, target_date):
        days = cls._days_until(target_date)
        if days is None:
            return 'missing'
        if days < 0:
            return 'expired'
        if days <= 30:
            return 'soon'
        return 'ok'

    @classmethod
    def _status_label(cls, status):
        return {
            'missing': 'Nesetat',
            'expired': 'Expirat',
            'soon': 'Expiră curând',
            'ok': 'În regulă',
        }[status]

    @classmethod
    def _status_badge(cls, status):
        return {
            'missing': 'secondary',
            'expired': 'danger',
            'soon': 'warning text-dark',
            'ok': 'success',
        }[status]

    def items(self):
        config = [
            ('ITP', 'itp_expiry', 'bi-clipboard2-check'),
            ('RCA', 'rca_expiry', 'bi-shield-check'),
            ('Rovinietă', 'rovinieta_expiry', 'bi-ticket-perforated'),
            ('Trusă', 'trusa_expiry', 'bi-bandaid'),
            ('Extinctor', 'extinctor_expiry', 'bi-fire-extinguisher'),
        ]
        data = []
        for label, field_name, icon in config:
            value = getattr(self, field_name)
            status = self._status_for_date(value)
            data.append({
                'label': label,
                'field_name': field_name,
                'icon': icon,
                'date': value,
                'days_left': self._days_until(value),
                'status': status,
                'status_label': self._status_label(status),
                'badge_class': self._status_badge(status),
            })
        return data

    def completion_count(self):
        return sum(1 for item in self.items() if item['date'])

    def overall_status(self):
        statuses = [item['status'] for item in self.items()]
        if 'expired' in statuses:
            return 'expired'
        if 'soon' in statuses:
            return 'soon'
        if self.completion_count() == 0:
            return 'missing'
        return 'ok'

    def nearest_expiry(self):
        dated_items = [item for item in self.items() if item['date']]
        if not dated_items:
            return None
        return min(dated_items, key=lambda item: item['date'])
