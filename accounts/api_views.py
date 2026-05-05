import json
import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .auth_api import (
    OAuthAccount,
    exchange_code_for_tokens,
    fetch_google_userinfo,
    get_or_create_user_for_oauth,
    json_response_user,
    merge_google_userinfo,
    normalize_email,
    provider_authorization_url,
    validate_oauth_state,
    verify_google_id_token,
)
from .models import EmailVerificationToken
from .views import _record_legal_acceptance


logger = logging.getLogger(__name__)


def _json_body(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except json.JSONDecodeError:
            raise ValidationError('JSON invalid.')
    return request.POST.dict()


def _success(user, *, created=False, next_url=''):
    payload = {'ok': True, 'user': json_response_user(user), 'created': created}
    if next_url:
        payload['next'] = next_url
    return JsonResponse(payload)


def _error(message, status=400):
    return JsonResponse({'ok': False, 'error': str(message)}, status=status)


def _client_ip(request):
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    return forwarded or request.META.get('REMOTE_ADDR') or 'unknown'


def _rate_limited(request, action, *, limit=20, window=300):
    key = f'auth-api-rate:{action}:{_client_ip(request)}'
    count = cache.get(key, 0) + 1
    cache.set(key, count, window)
    return count > limit


@require_http_methods(['POST'])
def register_api(request):
    if _rate_limited(request, 'register', limit=10):
        return _error('Prea multe incercari. Te rugam sa incerci din nou mai tarziu.', status=429)
    data = _json_body(request)
    email = normalize_email(data.get('email'))
    password = data.get('password') or data.get('password1') or ''
    password2 = data.get('password2') or password
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    username = (data.get('username') or email.split('@', 1)[0]).strip()
    if not email or not password:
        return _error('Emailul si parola sunt obligatorii.')
    if password != password2:
        return _error('Parolele nu coincid.')
    User = get_user_model()
    if User.objects.filter(email__iexact=email).exists():
        return _error('Exista deja un cont cu acest email.', status=409)
    base_username = username[:24] or 'user'
    candidate = base_username
    idx = 1
    while User.objects.filter(username__iexact=candidate).exists():
        idx += 1
        candidate = f'{base_username}_{idx}'[:30]
    user = User.objects.create_user(
        username=candidate,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    user.is_active = False
    user.save(update_fields=['is_active'])
    _record_legal_acceptance(user, request)
    EmailVerificationToken.objects.update_or_create(user=user)
    return JsonResponse({'ok': True, 'message': 'Contul tau a fost creat cu succes.', 'user': json_response_user(user)}, status=201)


@require_http_methods(['POST'])
def login_api(request):
    if _rate_limited(request, 'login', limit=20):
        return _error('Prea multe incercari. Te rugam sa incerci din nou mai tarziu.', status=429)
    data = _json_body(request)
    identifier = (data.get('email') or data.get('username') or '').strip()
    password = data.get('password') or ''
    User = get_user_model()
    username = identifier
    if '@' in identifier:
        user_by_email = User.objects.filter(email__iexact=normalize_email(identifier)).first()
        if user_by_email:
            username = user_by_email.username
    user = authenticate(request, username=username, password=password)
    if not user:
        return _error('Autentificare esuata. Te rugam sa incerci din nou.', status=401)
    login(request, user)
    return _success(user)


@require_http_methods(['POST'])
def logout_api(request):
    logout(request)
    return JsonResponse({'ok': True})


@require_http_methods(['GET'])
def me_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': True, 'user': None, 'is_authenticated': False})
    return JsonResponse({'ok': True, 'user': json_response_user(request.user), 'is_authenticated': True})


@require_http_methods(['GET', 'POST'])
def google_start_api(request):
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    try:
        url = provider_authorization_url(request, OAuthAccount.PROVIDER_GOOGLE, next_url=next_url)
    except ImproperlyConfigured as exc:
        return _error(exc, status=503)
    if request.GET.get('format') == 'json' or request.headers.get('Accept') == 'application/json':
        return JsonResponse({'ok': True, 'authorization_url': url})
    return redirect(url)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def google_callback_api(request):
    return _oauth_callback(request, OAuthAccount.PROVIDER_GOOGLE)


def _oauth_callback(request, provider):
    data = request.POST if request.method == 'POST' else request.GET
    try:
        if provider != OAuthAccount.PROVIDER_GOOGLE:
            raise ValidationError('Provider OAuth neacceptat.')
        next_url = validate_oauth_state(request, provider, data.get('state'))
        id_token = data.get('id_token') or data.get('identity_token')
        tokens = {}
        if not id_token and data.get('code'):
            tokens = exchange_code_for_tokens(provider, data.get('code'))
            id_token = tokens.get('id_token')
        if not id_token:
            return _error('Providerul nu a returnat identity token.', status=400)
        nonce = getattr(request, '_oauth_nonce', '') or request.session.pop(f'oauth_{provider}_nonce', '')
        identity = verify_google_id_token(id_token, nonce=nonce)
        if tokens.get('access_token'):
            identity = merge_google_userinfo(identity, fetch_google_userinfo(tokens['access_token']))
        user, _, created = get_or_create_user_for_oauth(identity)
        login(request, user)
        if request.headers.get('Accept') == 'application/json' or data.get('format') == 'json':
            return _success(user, created=created, next_url=next_url)
        return redirect(next_url or '/')
    except ValidationError as exc:
        return _error(exc.messages[0] if hasattr(exc, 'messages') else exc, status=400)
    except ImproperlyConfigured as exc:
        return _error(exc, status=503)
    except Exception as exc:
        logger.exception('Google OAuth callback failed')
        if getattr(settings, 'OAUTH_DEBUG_ERRORS', False):
            return _error(f'Autentificare esuata: {exc}', status=400)
        return _error('Autentificare esuata. Te rugam sa incerci din nou.', status=400)
