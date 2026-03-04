from django.conf import settings
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
