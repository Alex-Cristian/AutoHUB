from django.conf import settings
from django.db import models
from django.utils import timezone


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


class CarExpiryProfile(models.Model):
    STATUS_MISSING = 'missing'
    STATUS_EXPIRED = 'expired'
    STATUS_SOON = 'soon'
    STATUS_OK = 'ok'

    DOCUMENTS = [
        ('itp_expiry', 'ITP', 'bi-shield-check', 0),
        ('rca_expiry', 'RCA', 'bi-file-earmark-text', 30),
        ('rovinieta_expiry', 'Rovinietă', 'bi-sign-turn-right', 30),
        ('casco_expiry', 'CASCO', 'bi-shield-shaded', 30),
        ('trusa_expiry', 'Trusă auto', 'bi-bandaid', 30),
        ('extinctor_expiry', 'Extinctor', 'bi-fire', 30),
    ]

    car = models.OneToOneField(
        Car,
        on_delete=models.CASCADE,
        related_name='expiry_profile',
        verbose_name='Mașină',
    )
    itp_expiry = models.DateField(blank=True, null=True, verbose_name='Expirare ITP')
    rca_expiry = models.DateField(blank=True, null=True, verbose_name='Expirare RCA')
    rovinieta_expiry = models.DateField(blank=True, null=True, verbose_name='Expirare rovinietă')
    casco_expiry = models.DateField(blank=True, null=True, verbose_name='Expirare CASCO')
    trusa_expiry = models.DateField(blank=True, null=True, verbose_name='Expirare trusă auto')
    extinctor_expiry = models.DateField(blank=True, null=True, verbose_name='Expirare extinctor')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Calendar expirări mașină'
        verbose_name_plural = 'Calendare expirări mașini'

    def __str__(self):
        return f"Expirări documente - {self.car}"

    def get_document_items(self):
        today = timezone.localdate()
        items = []

        for field_name, label, icon, soon_days in self.DOCUMENTS:
            expiry_date = getattr(self, field_name)
            if not expiry_date:
                status = self.STATUS_MISSING
                days_left = None
            else:
                days_left = (expiry_date - today).days
                if days_left < 0:
                    status = self.STATUS_EXPIRED
                elif days_left <= soon_days:
                    status = self.STATUS_SOON
                else:
                    status = self.STATUS_OK

            items.append({
                'field': field_name,
                'label': label,
                'icon': icon,
                'date': expiry_date,
                'status': status,
                'days_left': days_left,
                'days_overdue': abs(days_left) if days_left is not None and days_left < 0 else 0,
            })

        return items

    def get_status_counts(self):
        counts = {
            self.STATUS_MISSING: 0,
            self.STATUS_EXPIRED: 0,
            self.STATUS_SOON: 0,
            self.STATUS_OK: 0,
        }
        for item in self.get_document_items():
            counts[item['status']] += 1
        return counts

    def get_dashboard_badge(self):
        counts = self.get_status_counts()
        if counts[self.STATUS_EXPIRED]:
            return {
                'label': f"{counts[self.STATUS_EXPIRED]} expirate",
                'class': 'danger',
                'icon': 'bi-exclamation-triangle-fill',
            }
        if counts[self.STATUS_SOON]:
            return {
                'label': f"{counts[self.STATUS_SOON]} curând",
                'class': 'warning',
                'icon': 'bi-alarm-fill',
            }
        if counts[self.STATUS_OK]:
            return {
                'label': 'Totul e ok',
                'class': 'success',
                'icon': 'bi-check-circle-fill',
            }
        return {
            'label': 'Nesetat',
            'class': 'secondary',
            'icon': 'bi-dash-circle',
        }
