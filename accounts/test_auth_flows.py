from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.forms import RegisterForm
from accounts.models import EmailVerificationToken, LegalAcceptance
from autohub_testutils.factories import make_email_verification, make_service_center, make_service_user, make_user


User = get_user_model()


class AccountAuthenticationFlowTests(TestCase):
    @patch("accounts.views.send_verification_email", return_value=True)
    def test_register_view_creates_inactive_user_legal_acceptance_and_verification_token(self, mocked_send):
        """Creeaza contul nou, acceptarea legala si tokenul de verificare fara a activa utilizatorul prematur."""
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Ion",
                "last_name": "Popescu",
                "username": "ionpopescu",
                "email": "ion@example.com",
                "password1": "ComplexPass123",
                "password2": "ComplexPass123",
                "accept_terms": "on",
            },
        )

        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(username="ionpopescu")
        self.assertFalse(user.is_active)
        self.assertTrue(LegalAcceptance.objects.filter(user=user).exists())
        self.assertTrue(EmailVerificationToken.objects.filter(user=user).exists())
        mocked_send.assert_called_once()

    def test_register_form_rejects_duplicate_email(self):
        """Respinge inregistrarea atunci cand emailul exista deja in sistem."""
        make_user(username="existing", email="duplicate@example.com")

        form = RegisterForm(
            data={
                "first_name": "Ana",
                "last_name": "Ionescu",
                "username": "alt-user",
                "email": "duplicate@example.com",
                "password1": "ComplexPass123",
                "password2": "ComplexPass123",
                "accept_terms": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_login_redirects_user_to_legal_acceptance_when_versions_are_missing(self):
        """Trimite utilizatorul catre acceptarea documentelor daca logarea reuseste dar acceptarea nu este actuala."""
        user = User.objects.create_user(
            username="noaccept",
            email="noaccept@example.com",
            password="pass12345",
            is_active=True,
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "noaccept", "password": "pass12345"},
        )

        self.assertRedirects(response, reverse("accounts:accept_legal"))

    def test_verify_email_activates_user_and_marks_token_verified(self):
        """Activeaza contul si marcheaza tokenul drept verificat atunci cand linkul este valid."""
        user = make_user(username="verifyme", active=False)
        token = make_email_verification(user)

        response = self.client.get(reverse("accounts:verify_email", args=[token.token]))

        self.assertRedirects(response, reverse("accounts:login"))
        user.refresh_from_db()
        token.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(token.verified_at)

    @patch("accounts.views.send_verification_email", return_value=True)
    def test_verify_email_regenerates_expired_token_and_resends_email(self, mocked_send):
        """Regeneraza tokenul expirat si trimite automat un nou email de verificare."""
        user = make_user(username="expired-user", active=False)
        token = make_email_verification(
            user,
            created_at=timezone.now() - timezone.timedelta(hours=48),
        )
        old_token_value = token.token

        response = self.client.get(reverse("accounts:verify_email", args=[token.token]))

        self.assertRedirects(response, reverse("accounts:login"))
        token.refresh_from_db()
        self.assertNotEqual(token.token, old_token_value)
        self.assertIsNone(token.verified_at)
        mocked_send.assert_called_once()

    def test_logout_view_ends_session_and_redirects_home(self):
        """Deconecteaza utilizatorul si il trimite inapoi pe homepage."""
        user = make_user(username="logout-user")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class AccountRoleRoutingTests(TestCase):
    def test_service_owner_home_redirects_to_service_dashboard(self):
        """Redirectioneaza proprietarul de service din homepage direct catre dashboardul operational."""
        owner = make_service_user(username="service-owner")
        make_service_center(owner=owner, name="Service Redirect")
        self.client.force_login(owner)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(response, reverse("services:dashboard"))

    def test_profile_requires_authentication(self):
        """Cere autentificare pentru accesarea profilului utilizatorului."""
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
