from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class LegalAcceptanceRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        if response is not None:
            return response
        return self.get_response(request)

    def process_request(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None

        exempt_paths = {
            reverse('accounts:accept_legal'),
            reverse('accounts:logout'),
            reverse('accounts:login'),
            reverse('accounts:register'),
            reverse('services:register_public'),
            reverse('core:terms'),
            reverse('core:privacy'),
            reverse('core:cookies'),
        }

        path = request.path
        if path.startswith('/admin/') or path.startswith(settings.STATIC_URL) or path.startswith('/media/'):
            return None
        if path in exempt_paths:
            return None

        acceptance = getattr(user, 'legal_acceptance', None)
        current = settings.LEGAL_DOCUMENTS_VERSION
        is_current = bool(acceptance and acceptance.terms_version == current and acceptance.privacy_version == current and acceptance.cookies_version == current)
        if is_current:
            return None

        accept_url = reverse('accounts:accept_legal')
        if request.get_full_path() == accept_url:
            return None
        return redirect(f'{accept_url}?next={request.get_full_path()}')
