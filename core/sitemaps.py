from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from services.models import ServiceCenter


class CanonicalDomainSitemap(Sitemap):
    protocol = "https"

    def get_domain(self, site=None):
        return urlparse(settings.CANONICAL_SITE_URL).netloc or settings.CANONICAL_HOST


class StaticPagesSitemap(CanonicalDomainSitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return [
            "core:home",
            "core:about",
            "services:list",
            "services:categories",
            "core:terms",
            "core:privacy",
            "core:cookies",
        ]

    def location(self, item):
        return reverse(item)


class ServiceSitemap(CanonicalDomainSitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return ServiceCenter.objects.filter(is_active=True).order_by("name")

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)
