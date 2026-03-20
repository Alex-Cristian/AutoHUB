from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import CarExpiryProfile, CarExpiryReminderLog
from core.services.email_service import send_expiry_reminder_email


class Command(BaseCommand):
    help = 'Trimite emailuri pentru documentele auto care expiră aproximativ într-o lună.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        sent_count = 0
        skipped_count = 0

        profiles = CarExpiryProfile.objects.select_related('car', 'car__owner')

        for profile in profiles:
            car = profile.car
            user = car.owner
            if not user.email:
                skipped_count += 1
                continue

            for field_name, label, _icon, _soon_days in profile.DOCUMENTS:
                expiry_date = getattr(profile, field_name)
                if not expiry_date:
                    continue
                days_left = (expiry_date - today).days
                if not 28 <= days_left <= 31:
                    continue
                already_sent = CarExpiryReminderLog.objects.filter(
                    car=car,
                    document_type=field_name,
                    expiry_date=expiry_date,
                ).exists()
                if already_sent:
                    continue

                if send_expiry_reminder_email(user, car, label, expiry_date):
                    with transaction.atomic():
                        CarExpiryReminderLog.objects.get_or_create(
                            car=car,
                            document_type=field_name,
                            expiry_date=expiry_date,
                        )
                    sent_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Emailuri trimise: {sent_count}. Elemente sărite: {skipped_count}.'
        ))
