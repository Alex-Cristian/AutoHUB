from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.auth_api import OAUTH_STATE_SALT
from accounts.models import EmailVerificationToken, OAuthAccount


User = get_user_model()


class AuthApiTests(TestCase):
    def _set_oauth_session(self, provider, state='state-ok', nonce='nonce-ok', next_url='/services/dashboard/'):
        signed_state = signing.dumps({
            'provider': provider,
            'nonce': nonce,
            'next': next_url,
            'csrf': state,
        }, salt=OAUTH_STATE_SALT)
        session = self.client.session
        session[f'oauth_{provider}_state'] = signed_state
        session[f'oauth_{provider}_nonce'] = nonce
        session[f'oauth_{provider}_next'] = next_url
        session.save()
        return signed_state

    def _google_identity(self, **overrides):
        payload = {
            'provider': OAuthAccount.PROVIDER_GOOGLE,
            'provider_user_id': 'google-sub-1',
            'email': 'driver@example.com',
            'email_verified': True,
            'name': 'Driver Google',
            'first_name': 'Driver',
            'last_name': 'Google',
            'avatar_url': 'https://example.com/avatar.png',
        }
        payload.update(overrides)
        return payload

    def test_register_classic_api_creates_inactive_user_and_verification_token(self):
        response = self.client.post(reverse('accounts_api:register'), {
            'email': 'new.api@example.com',
            'username': 'newapi',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'first_name': 'New',
            'last_name': 'Api',
        }, content_type='application/json')

        user = User.objects.get(email='new.api@example.com')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(user.is_active)
        self.assertTrue(EmailVerificationToken.objects.filter(user=user).exists())

    def test_login_classic_api_creates_session(self):
        user = User.objects.create_user(username='classic', email='classic@example.com', password='StrongPass123!')

        response = self.client.post(reverse('accounts_api:login'), {
            'email': 'classic@example.com',
            'password': 'StrongPass123!',
        }, content_type='application/json')
        me = self.client.get(reverse('accounts_api:me')).json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(me['user']['id'], user.pk)

    def test_logout_api_clears_session(self):
        User.objects.create_user(username='logoutapi', email='logout@example.com', password='StrongPass123!')
        self.client.post(reverse('accounts_api:login'), {
            'email': 'logout@example.com',
            'password': 'StrongPass123!',
        }, content_type='application/json')

        response = self.client.post(reverse('accounts_api:logout'))
        me = self.client.get(reverse('accounts_api:me')).json()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(me['user'])

    def test_me_api_returns_current_user(self):
        user = User.objects.create_user(username='meapi', email='me@example.com', password='StrongPass123!')
        self.client.force_login(user)

        response = self.client.get(reverse('accounts_api:me')).json()

        self.assertTrue(response['is_authenticated'])
        self.assertEqual(response['user']['email'], 'me@example.com')

    @patch('accounts.api_views.verify_google_id_token')
    def test_google_login_with_valid_token_creates_new_user(self, mocked_verify):
        mocked_verify.return_value = self._google_identity()
        state = self._set_oauth_session(OAuthAccount.PROVIDER_GOOGLE)

        response = self.client.post(reverse('accounts_api:google_callback'), {
            'state': state,
            'id_token': 'valid-google-token',
            'format': 'json',
        }, HTTP_ACCEPT='application/json')

        user = User.objects.get(email='driver@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(OAuthAccount.objects.filter(user=user, provider='google', provider_user_id='google-sub-1').exists())
        self.assertEqual(self.client.get(reverse('accounts_api:me')).json()['user']['id'], user.pk)

    @patch('accounts.api_views.fetch_google_userinfo')
    @patch('accounts.api_views.verify_google_id_token')
    @patch('accounts.api_views.exchange_code_for_tokens')
    def test_google_callback_with_valid_code_exchanges_token_and_logs_in(self, mocked_exchange, mocked_verify, mocked_userinfo):
        mocked_exchange.return_value = {'id_token': 'valid-google-token', 'access_token': 'google-access-token'}
        mocked_verify.return_value = self._google_identity(provider_user_id='google-sub-code', email='code@example.com')
        mocked_userinfo.return_value = {
            'sub': 'google-sub-code',
            'email': 'code@example.com',
            'email_verified': True,
            'name': 'Code Google',
            'given_name': 'Code',
            'family_name': 'Google',
            'picture': 'https://example.com/code.png',
        }
        state = self._set_oauth_session(OAuthAccount.PROVIDER_GOOGLE)

        response = self.client.get(reverse('accounts_api:google_callback'), {
            'state': state,
            'code': 'valid-code',
            'format': 'json',
        }, HTTP_ACCEPT='application/json')

        user = User.objects.get(email='code@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse('accounts_api:me')).json()['user']['id'], user.pk)
        mocked_exchange.assert_called_once_with(OAuthAccount.PROVIDER_GOOGLE, 'valid-code')
        mocked_userinfo.assert_called_once_with('google-access-token')

    @patch('accounts.api_views.verify_google_id_token', side_effect=Exception('bad token'))
    def test_google_login_with_invalid_token_is_rejected(self, _mocked_verify):
        state = self._set_oauth_session(OAuthAccount.PROVIDER_GOOGLE)

        response = self.client.post(reverse('accounts_api:google_callback'), {
            'state': state,
            'id_token': 'invalid-google-token',
            'format': 'json',
        }, HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='driver@example.com').exists())

    @patch('accounts.api_views.verify_google_id_token')
    def test_existing_verified_email_is_linked_to_google(self, mocked_verify):
        user = User.objects.create_user(username='existinggoogle', email='same@example.com', password='StrongPass123!')
        mocked_verify.return_value = self._google_identity(email='same@example.com', email_verified=True)
        state = self._set_oauth_session(OAuthAccount.PROVIDER_GOOGLE)

        response = self.client.post(reverse('accounts_api:google_callback'), {
            'state': state,
            'id_token': 'valid-google-token',
            'format': 'json',
        }, HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(OAuthAccount.objects.filter(user=user, provider='google').exists())

    @patch('accounts.api_views.verify_google_id_token')
    def test_existing_provider_user_id_logs_into_same_account(self, mocked_verify):
        user = User.objects.create_user(username='providerknown', email='known@example.com', password='StrongPass123!')
        OAuthAccount.objects.create(
            user=user,
            provider=OAuthAccount.PROVIDER_GOOGLE,
            provider_user_id='google-sub-known',
            provider_email='known@example.com',
            email_verified=True,
        )
        mocked_verify.return_value = self._google_identity(
            provider_user_id='google-sub-known',
            email='changed@example.com',
            email_verified=True,
        )
        state = self._set_oauth_session(OAuthAccount.PROVIDER_GOOGLE)

        response = self.client.post(reverse('accounts_api:google_callback'), {
            'state': state,
            'id_token': 'valid-google-token',
            'format': 'json',
        }, HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse('accounts_api:me')).json()['user']['id'], user.pk)
        self.assertFalse(User.objects.filter(email='changed@example.com').exists())

    @patch('accounts.api_views.verify_google_id_token')
    def test_unverified_provider_email_does_not_link_existing_account(self, mocked_verify):
        User.objects.create_user(username='unverifiedlink', email='unsafe@example.com', password='StrongPass123!')
        mocked_verify.return_value = self._google_identity(email='unsafe@example.com', email_verified=False)
        state = self._set_oauth_session(OAuthAccount.PROVIDER_GOOGLE)

        response = self.client.post(reverse('accounts_api:google_callback'), {
            'state': state,
            'id_token': 'valid-google-token',
            'format': 'json',
        }, HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(OAuthAccount.objects.filter(provider_email='unsafe@example.com').exists())

    @patch('accounts.api_views.verify_google_id_token')
    def test_callback_without_valid_state_is_rejected(self, mocked_verify):
        mocked_verify.return_value = self._google_identity()
        self._set_oauth_session(OAuthAccount.PROVIDER_GOOGLE, state='expected-state')

        response = self.client.post(reverse('accounts_api:google_callback'), {
            'state': 'wrong-state',
            'id_token': 'valid-google-token',
            'format': 'json',
        }, HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, 400)
        mocked_verify.assert_not_called()

    @patch('accounts.api_views.verify_google_id_token')
    def test_google_callback_accepts_signed_state_without_session_cookie(self, mocked_verify):
        mocked_verify.return_value = self._google_identity(provider_user_id='google-stateless', email='stateless@example.com')
        state = signing.dumps({
            'provider': OAuthAccount.PROVIDER_GOOGLE,
            'nonce': 'nonce-from-state',
            'next': '/bookings/programarile-mele/',
            'csrf': 'random-state-token',
        }, salt=OAUTH_STATE_SALT)

        response = self.client.post(reverse('accounts_api:google_callback'), {
            'state': state,
            'id_token': 'valid-google-token',
            'format': 'json',
        }, HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='stateless@example.com').exists())
        mocked_verify.assert_called_once_with('valid-google-token', nonce='nonce-from-state')

    @override_settings(GOOGLE_CLIENT_ID='google-client', GOOGLE_CLIENT_SECRET='google-secret')
    def test_start_google_oauth_builds_secure_authorization_url_and_preserves_redirect(self):
        start = self.client.get(
            reverse('accounts_api:google'),
            {'next': '/bookings/programarile-mele/'},
        )
        self.assertEqual(start.status_code, 302)
        parsed = urlparse(start['Location'])
        params = parse_qs(parsed.query)
        self.assertEqual(f'{parsed.scheme}://{parsed.netloc}{parsed.path}', 'https://accounts.google.com/o/oauth2/v2/auth')
        self.assertEqual(params['client_id'], ['google-client'])
        self.assertEqual(params['response_type'], ['code'])
        self.assertEqual(params['scope'], ['openid email profile'])
        self.assertTrue(params.get('state'))
        self.assertTrue(params.get('nonce'))
        session = self.client.session
        self.assertEqual(session['oauth_google_next'], '/bookings/programarile-mele/')

    @override_settings(GOOGLE_CLIENT_ID='google-client', GOOGLE_CLIENT_SECRET='google-secret')
    def test_login_ui_shows_google_button_and_no_apple_button(self):
        response = self.client.get(reverse('accounts:login'))
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('login-google-button', content)
        self.assertIn('Continuă cu Google', content)
        self.assertNotIn('login-apple-button', content)
        self.assertNotIn('Continuă cu Apple', content)

    @override_settings(GOOGLE_CLIENT_ID='google-client', GOOGLE_CLIENT_SECRET='google-secret')
    def test_register_ui_shows_google_button_and_no_apple_button(self):
        response = self.client.get(reverse('accounts:register'))
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('register-google-button', content)
        self.assertIn('Continuă cu Google', content)
        self.assertNotIn('register-apple-button', content)
        self.assertNotIn('Continuă cu Apple', content)
