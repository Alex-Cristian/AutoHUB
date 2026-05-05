import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from .models import LegalAcceptance, OAuthAccount


GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://openidconnect.googleapis.com/v1/userinfo'
GOOGLE_CERTS_URL = 'https://www.googleapis.com/oauth2/v3/certs'
GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'
OAUTH_STATE_MAX_AGE_SECONDS = 600
OAUTH_STATE_SALT = 'accounts.oauth.state'


def normalize_email(email):
    return (email or '').strip().lower()


def json_response_user(user):
    return {
        'id': user.pk,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'name': user.get_full_name() or user.username,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'is_authenticated': True,
    }


def app_url(path=''):
    base = getattr(settings, 'APP_URL', '') or getattr(settings, 'SITE_BASE_URL', 'http://127.0.0.1:8000')
    return base.rstrip('/') + '/' + path.lstrip('/')


def configured_redirect_uri(provider):
    if provider == OAuthAccount.PROVIDER_GOOGLE:
        return getattr(settings, 'GOOGLE_REDIRECT_URI', '') or app_url(reverse('accounts_api:google_callback'))
    raise ValueError('Provider necunoscut.')


def provider_config(provider):
    if provider == OAuthAccount.PROVIDER_GOOGLE:
        return {
            'client_id': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'GOOGLE_CLIENT_SECRET', ''),
            'redirect_uri': configured_redirect_uri(provider),
            'auth_url': getattr(settings, 'GOOGLE_AUTHORIZATION_URL', GOOGLE_AUTH_URL),
            'token_url': getattr(settings, 'GOOGLE_TOKEN_URL', GOOGLE_TOKEN_URL),
            'userinfo_url': getattr(settings, 'GOOGLE_USERINFO_URL', GOOGLE_USERINFO_URL),
            'jwks_url': getattr(settings, 'GOOGLE_JWKS_URL', GOOGLE_CERTS_URL),
            'discovery_url': getattr(settings, 'GOOGLE_DISCOVERY_URL', GOOGLE_DISCOVERY_URL),
            'scope': 'openid email profile',
        }
    raise ValueError('Provider necunoscut.')


def ensure_provider_config(provider):
    config = provider_config(provider)
    missing = [key for key in ('client_id', 'client_secret', 'redirect_uri') if not config.get(key)]
    if missing:
        raise ImproperlyConfigured(f'Configuratie OAuth incompleta pentru {provider}: {", ".join(missing)}')
    return config


def generate_oauth_state(request, provider, next_url=''):
    nonce = secrets.token_urlsafe(32)
    state = signing.dumps(
        {
            'provider': provider,
            'nonce': nonce,
            'next': next_url or '',
            'csrf': secrets.token_urlsafe(32),
        },
        salt=OAUTH_STATE_SALT,
        compress=True,
    )
    request.session[f'oauth_{provider}_state'] = state
    request.session[f'oauth_{provider}_nonce'] = nonce
    request.session[f'oauth_{provider}_next'] = next_url or ''
    return state, nonce


def validate_oauth_state(request, provider, state):
    if state:
        try:
            payload = signing.loads(
                state,
                salt=OAUTH_STATE_SALT,
                max_age=OAUTH_STATE_MAX_AGE_SECONDS,
            )
        except signing.BadSignature:
            payload = None
        if payload and payload.get('provider') == provider and payload.get('nonce'):
            request._oauth_nonce = payload['nonce']
            return payload.get('next') or ''

    expected = request.session.pop(f'oauth_{provider}_state', '')
    if not expected or not state or not secrets.compare_digest(expected, state):
        raise ValidationError('State OAuth invalid sau expirat.')
    request._oauth_nonce = request.session.pop(f'oauth_{provider}_nonce', '')
    return request.session.pop(f'oauth_{provider}_next', '')


def provider_authorization_url(request, provider, next_url=''):
    config = ensure_provider_config(provider)
    state, nonce = generate_oauth_state(request, provider, next_url=next_url)
    params = {
        'client_id': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'response_type': 'code',
        'scope': config['scope'],
        'state': state,
        'nonce': nonce,
    }
    return f"{config['auth_url']}?{urlencode(params)}"


def exchange_code_for_tokens(provider, code):
    config = ensure_provider_config(provider)
    response = requests.post(config['token_url'], data={
        'client_id': config['client_id'],
        'client_secret': config['client_secret'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': config['redirect_uri'],
    }, timeout=15)
    if response.status_code >= 400:
        try:
            data = response.json()
        except ValueError:
            data = {}
        detail = data.get('error_description') or data.get('error') or response.text or response.reason
        raise ValidationError(f'Google token endpoint a respins codul: {detail}')
    return response.json()


def fetch_google_userinfo(access_token):
    if not access_token:
        return {}
    config = provider_config(OAuthAccount.PROVIDER_GOOGLE)
    response = requests.get(
        config['userinfo_url'],
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=15,
    )
    if response.status_code >= 400:
        try:
            data = response.json()
        except ValueError:
            data = {}
        detail = data.get('error_description') or data.get('error') or response.text or response.reason
        raise ValidationError(f'Google UserInfo a respins access token-ul: {detail}')
    return response.json()


def merge_google_userinfo(identity, userinfo):
    if not userinfo:
        return identity
    if userinfo.get('sub') and identity.get('provider_user_id') and userinfo['sub'] != identity['provider_user_id']:
        raise ValidationError('UserInfo Google nu corespunde identity token-ului.')
    identity['email'] = identity.get('email') or normalize_email(userinfo.get('email'))
    identity['email_verified'] = identity.get('email_verified') or userinfo.get('email_verified') is True or userinfo.get('email_verified') == 'true'
    identity['name'] = identity.get('name') or userinfo.get('name', '')
    identity['first_name'] = identity.get('first_name') or userinfo.get('given_name', '')
    identity['last_name'] = identity.get('last_name') or userinfo.get('family_name', '')
    identity['avatar_url'] = identity.get('avatar_url') or userinfo.get('picture', '')
    return identity


def _load_jwt_library():
    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as exc:
        raise ImproperlyConfigured('Instaleaza PyJWT[crypto] pentru validarea OIDC id_token.') from exc
    return jwt, PyJWKClient


def verify_oidc_id_token(id_token, *, issuer, audience, jwks_url, nonce=''):
    jwt, PyJWKClient = _load_jwt_library()
    try:
        signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=['RS256'],
            audience=audience,
            issuer=issuer,
            options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']},
        )
    except Exception as exc:
        raise ValidationError(f'Identity token Google invalid: {exc}') from exc
    if nonce and claims.get('nonce') != nonce:
        raise ValidationError('Nonce OIDC invalid.')
    return claims


def verify_google_id_token(id_token, nonce=''):
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    config = provider_config(OAuthAccount.PROVIDER_GOOGLE)
    claims = verify_oidc_id_token(
        id_token,
        issuer='https://accounts.google.com',
        audience=client_id,
        jwks_url=config['jwks_url'],
        nonce=nonce,
    )
    return {
        'provider': OAuthAccount.PROVIDER_GOOGLE,
        'provider_user_id': claims.get('sub', ''),
        'email': normalize_email(claims.get('email')),
        'email_verified': claims.get('email_verified') is True or claims.get('email_verified') == 'true',
        'name': claims.get('name', ''),
        'first_name': claims.get('given_name', ''),
        'last_name': claims.get('family_name', ''),
        'avatar_url': claims.get('picture', ''),
    }


def _username_from_email(email):
    User = get_user_model()
    base = (email.split('@', 1)[0] or 'user').replace('.', '_')[:24]
    candidate = base
    idx = 1
    while User.objects.filter(username__iexact=candidate).exists():
        idx += 1
        candidate = f'{base}_{idx}'[:30]
    return candidate


def _mark_email_verified(user):
    from .models import EmailVerificationToken

    EmailVerificationToken.objects.update_or_create(
        user=user,
        defaults={'token': secrets.token_urlsafe(32), 'verified_at': timezone.now()},
    )


def _record_default_legal_acceptance(user):
    LegalAcceptance.objects.update_or_create(
        user=user,
        defaults={
            'document_set': 'platform',
            'terms_version': settings.LEGAL_DOCUMENTS_VERSION,
            'privacy_version': settings.LEGAL_DOCUMENTS_VERSION,
            'cookies_version': settings.LEGAL_DOCUMENTS_VERSION,
            'accepted_at': timezone.now(),
        },
    )


def get_or_create_user_for_oauth(identity):
    provider = identity['provider']
    provider_user_id = identity.get('provider_user_id')
    email = normalize_email(identity.get('email'))
    email_verified = bool(identity.get('email_verified'))
    if not provider_user_id:
        raise ValidationError('Tokenul providerului nu contine un identificator valid.')

    account = OAuthAccount.objects.select_related('user').filter(
        provider=provider,
        provider_user_id=provider_user_id,
    ).first()
    if account:
        _update_oauth_account(account, identity)
        return account.user, account, False

    if not email:
        raise ValidationError('Providerul nu a returnat un email valid.')

    User = get_user_model()
    existing_user = User.objects.filter(email__iexact=email).first()
    if existing_user:
        if not email_verified:
            raise ValidationError('Exista deja un cont cu acest email. Conecteaza-te cu metoda folosita initial sau leaga contul din setari.')
        user = existing_user
        created = False
    else:
        user = User.objects.create_user(
            username=_username_from_email(email),
            email=email,
            password=None,
            first_name=(identity.get('first_name') or '').strip(),
            last_name=(identity.get('last_name') or '').strip(),
        )
        user.is_active = True
        user.save(update_fields=['is_active'])
        created = True
        _record_default_legal_acceptance(user)

    if email_verified:
        _mark_email_verified(user)

    changed_fields = []
    if identity.get('first_name') and not user.first_name:
        user.first_name = identity['first_name']
        changed_fields.append('first_name')
    if identity.get('last_name') and not user.last_name:
        user.last_name = identity['last_name']
        changed_fields.append('last_name')
    if changed_fields:
        user.save(update_fields=changed_fields)

    account = OAuthAccount.objects.create(
        user=user,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_email=email,
        email_verified=email_verified,
        name=(identity.get('name') or '').strip(),
        avatar_url=(identity.get('avatar_url') or '').strip(),
    )
    return user, account, created


def _update_oauth_account(account, identity):
    fields = []
    email = normalize_email(identity.get('email'))
    if email and account.provider_email != email:
        account.provider_email = email
        fields.append('provider_email')
    email_verified = bool(identity.get('email_verified'))
    if account.email_verified != email_verified:
        account.email_verified = email_verified
        fields.append('email_verified')
    name = (identity.get('name') or '').strip()
    if name and account.name != name:
        account.name = name
        fields.append('name')
    avatar_url = (identity.get('avatar_url') or '').strip()
    if avatar_url and account.avatar_url != avatar_url:
        account.avatar_url = avatar_url
        fields.append('avatar_url')
    if fields:
        account.save(update_fields=[*fields, 'updated_at'])
