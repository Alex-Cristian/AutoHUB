from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import ServiceCenter, ServiceCategory


class StaticViewSitemap(Sitemap):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return ["core:home", "core:about", "services:list", "services:categories"]

    def location(self, item):
        return reverse(item)


class ServiceCenterSitemap(Sitemap):
    priority = 0.9
    changefreq = "daily"

    def items(self):
        return ServiceCenter.objects.filter(is_active=True).order_by("-updated_at", "name") if hasattr(ServiceCenter, "updated_at") else ServiceCenter.objects.filter(is_active=True).order_by("name")

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)


class ServiceCategorySitemap(Sitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return ServiceCategory.objects.order_by("order", "name")
