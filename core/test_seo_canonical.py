from django.test import TestCase, override_settings


SEO_SETTINGS = {
    "ALLOWED_HOSTS": ["autoemg.com", "www.autoemg.com", "testserver"],
    "CANONICAL_HOST": "autoemg.com",
    "CANONICAL_SITE_URL": "https://autoemg.com",
    "CANONICAL_REDIRECT_HOSTS": ["autoemg.com", "www.autoemg.com"],
    "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
    "SECURE_SSL_REDIRECT": True,
}


@override_settings(**SEO_SETTINGS)
class SeoCanonicalTests(TestCase):
    def test_sitemap_uses_only_canonical_https_host(self):
        response = self.client.get(
            "/sitemap.xml",
            HTTP_HOST="autoemg.com",
            HTTP_X_FORWARDED_PROTO="https",
        )

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertNotIn("example.com", body)
        self.assertIn("https://autoemg.com/", body)
        self.assertNotIn("http://autoemg.com", body)
        self.assertNotIn("https://www.autoemg.com", body)

    def test_www_to_non_www_redirect_does_not_loop(self):
        response = self.client.get(
            "/",
            follow=True,
            HTTP_HOST="www.autoemg.com",
            HTTP_X_FORWARDED_PROTO="https",
        )

        self.assertEqual(response.redirect_chain, [("https://autoemg.com/", 301)])
        self.assertEqual(response.status_code, 200)

    def test_public_variants_redirect_directly_to_canonical_homepage(self):
        cases = [
            ("autoemg.com", "http", "https://autoemg.com/"),
            ("www.autoemg.com", "http", "https://autoemg.com/"),
            ("www.autoemg.com", "https", "https://autoemg.com/"),
        ]

        for host, proto, expected_location in cases:
            with self.subTest(host=host, proto=proto):
                response = self.client.get(
                    "/",
                    HTTP_HOST=host,
                    HTTP_X_FORWARDED_PROTO=proto,
                )

                self.assertEqual(response.status_code, 301)
                self.assertEqual(response["Location"], expected_location)

    def test_canonical_https_homepage_returns_200(self):
        response = self.client.get(
            "/",
            HTTP_HOST="autoemg.com",
            HTTP_X_FORWARDED_PROTO="https",
        )

        self.assertEqual(response.status_code, 200)
