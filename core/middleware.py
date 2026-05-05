from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class LegalAcceptanceRequiredMiddleware:
    """
    Verifică dacă userul autentificat a acceptat documentele legale curente.

    Optimizări:
    - reverse() calculat o singură dată la startup
    - legal_acceptance verificat din cache Django (fără query extra dacă
      userul a fost încărcat cu select_related('legal_acceptance'))
    - rezultatul verificării cached pe obiectul request pentru durata request-ului
    """

    def __init__(self, get_response):
        self.get_response = get_response
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
        self._legal_version = None  # cache versiune documente

    def __call__(self, request):
        response = self.process_request(request)
        if response is not None:
            return response
        return self.get_response(request)

    def _get_legal_version(self):
        """Cache versiunea documentelor legale — nu se schimbă în runtime."""
        if self._legal_version is None:
            self._legal_version = settings.LEGAL_DOCUMENTS_VERSION
        return self._legal_version

    def process_request(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None

        path = request.path

        # Bypass rapid pentru static/admin/media/API auth
        if path.startswith('/admin/') or path.startswith('/media/') or path.startswith('/api/auth/'):
            return None
        static_url = settings.STATIC_URL
        if static_url and path.startswith(static_url):
            return None

        if path in self._exempt_paths:
            return None

        # Folosește cache-ul Django pentru related objects
        # Dacă userul a fost încărcat cu select_related('legal_acceptance'),
        # nu se mai face niciun query suplimentar aici
        try:
            acceptance = user.legal_acceptance
        except Exception:
            acceptance = None

        current = self._get_legal_version()
        if acceptance and (
            acceptance.terms_version == current
            and acceptance.privacy_version == current
            and acceptance.cookies_version == current
        ):
            return None

        return redirect(f'{self._accept_url}?next={request.get_full_path()}')
