from django.test import TestCase
from django.urls import reverse

from autohub_testutils.factories import make_service_center, make_service_item


class ServiceApiEndpointTests(TestCase):
    def test_services_api_filters_public_results(self):
        """Returneaza doar service-urile care respecta filtrele publice cerute in querystring."""
        matching = make_service_center(name="Diagnoza Bucuresti", city="bucuresti")
        make_service_item(center=matching, price_from=100, price_to=200)
        non_matching = make_service_center(name="Detailing Cluj", city="cluj-napoca")
        make_service_item(center=non_matching, price_from=300, price_to=400)

        response = self.client.get(
            reverse("api_services"),
            {"city": "bucuresti", "q": "Diagnoza"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], matching.pk)

    def test_services_nearby_requires_coordinates_and_sorts_results(self):
        """Valideaza coordonatele pentru endpointul nearby si ordoneaza service-urile dupa distanta."""
        close_center = make_service_center(name="Service Aproape")
        close_center.latitude = 44.4300
        close_center.longitude = 26.1000
        close_center.save(update_fields=["latitude", "longitude"])

        far_center = make_service_center(name="Service Departe")
        far_center.latitude = 44.9000
        far_center.longitude = 26.5000
        far_center.save(update_fields=["latitude", "longitude"])

        bad_response = self.client.get(reverse("api_services_nearby"))
        good_response = self.client.get(
            reverse("api_services_nearby"),
            {"lat": "44.431", "lng": "26.101", "radius": "20"},
        )

        self.assertEqual(bad_response.status_code, 400)
        payload = good_response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], close_center.pk)
