from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import LegalAcceptance


User = get_user_model()


class LegalAcceptanceMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='client1',
            email='client1@example.com',
            password='pass12345',
        )

    def test_authenticated_user_without_acceptance_is_redirected(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('accounts:profile'))

        self.assertRedirects(
            response,
            f"{reverse('accounts:accept_legal')}?next={reverse('accounts:profile')}",
            fetch_redirect_response=False,
        )

    def test_authenticated_user_with_acceptance_can_access_page(self):
        LegalAcceptance.objects.create(
            user=self.user,
            document_set='platform',
            terms_version=settings.LEGAL_DOCUMENTS_VERSION,
            privacy_version=settings.LEGAL_DOCUMENTS_VERSION,
            cookies_version=settings.LEGAL_DOCUMENTS_VERSION,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('accounts:profile'))

        self.assertEqual(response.status_code, 200)
