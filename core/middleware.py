from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class LegalAcceptanceRequiredMiddleware:
    """
    Verifică dacă userul autentificat a acceptat documentele legale curente.

    Optimizare: URL-urile exempt sunt calculate O SINGURĂ DATĂ la startup
    (în __init__), nu la fiecare request — elimină 6x reverse() per request.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # reverse() apelat o singură dată la pornirea serverului
        self._exempt_paths = frozenset([
            reverse('accounts:accept_legal'),
            reverse('accounts:logout'),
            reverse('accounts:login'),
            reverse('accounts:register'),
            reverse('services:register_public'),
            reverse('core:terms'),
            reverse('core:privacy'),
            reverse('core:cookies'),
        ])
        self._accept_url = reverse('accounts:accept_legal')

    def __call__(self, request):
        response = self.process_request(request)
        if response is not None:
            return response
        return self.get_response(request)

    def process_request(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None

        path = request.path

        # Bypass rapid pentru static/admin/media
        if path.startswith('/admin/') or path.startswith('/media/'):
            return None
        static_url = settings.STATIC_URL
        if static_url and path.startswith(static_url):
            return None

        if path in self._exempt_paths:
            return None

        acceptance = getattr(user, 'legal_acceptance', None)
        current = settings.LEGAL_DOCUMENTS_VERSION
        if acceptance and (
            acceptance.terms_version == current
            and acceptance.privacy_version == current
            and acceptance.cookies_version == current
        ):
            return None

        return redirect(f'{self._accept_url}?next={request.get_full_path()}')