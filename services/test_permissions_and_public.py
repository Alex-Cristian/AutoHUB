from django.test import TestCase
from django.urls import reverse

from bookings.models import Booking
from services.models import Favorite, Review
from autohub_testutils.factories import (
    make_admin_user,
    make_booking,
    make_client_user,
    make_service_center,
    make_service_user,
)


class ServicePermissionBoundaryTests(TestCase):
    def test_plain_client_is_redirected_away_from_service_dashboard(self):
        """Nu permite unui client simplu sa intre in dashboardul intern al service-ului."""
        client_user = make_client_user(username="plain-client")
        self.client.force_login(client_user)

        response = self.client.get(reverse("services:dashboard"))

        self.assertRedirects(response, reverse("services:register_service"))

    def test_service_owner_cannot_open_other_service_booking_detail(self):
        """Izoleaza datele operationale intre service-uri diferite."""
        owner_one = make_service_user(username="owner-one")
        owner_two = make_service_user(username="owner-two")
        center_two = make_service_center(owner=owner_two, name="Service Two")
        foreign_booking = make_booking(center=center_two, status=Booking.STATUS_CONFIRMED)
        self.client.force_login(owner_one)

        response = self.client.get(reverse("services:booking_detail", args=[foreign_booking.pk]))

        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)

    def test_admin_can_still_access_verification_and_private_service_pages(self):
        """Pastreaza accesul administratorului pentru zonele interne de moderare si operare."""
        admin = make_admin_user(username="staff-admin")
        owner = make_service_user(username="owner-admin-check")
        center = make_service_center(owner=owner, name="Service Moderat")
        booking = make_booking(center=center, status=Booking.STATUS_CONFIRMED)
        self.client.force_login(admin)

        verification_response = self.client.get(reverse("services:verification_list"))
        booking_response = self.client.get(reverse("services:booking_detail", args=[booking.pk]))

        self.assertEqual(verification_response.status_code, 200)
        self.assertEqual(booking_response.status_code, 200)


class PublicServicePagesTests(TestCase):
    def test_homepage_and_service_list_render_public_content(self):
        """Livreaza homepage-ul si lista publica de service-uri fara autentificare."""
        center = make_service_center(name="Public Service", is_featured=True)

        home_response = self.client.get(reverse("core:home"))
        list_response = self.client.get(reverse("services:list"), {"q": "Public"})

        self.assertEqual(home_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, center.name)

    def test_service_detail_marks_can_review_only_after_completed_booking(self):
        """Arata corect eligibilitatea pentru recenzii doar clientilor cu lucrare finalizata."""
        center = make_service_center(name="Review Service")
        user = make_client_user(username="review-candidate")
        self.client.force_login(user)

        first_response = self.client.get(reverse("services:detail", args=[center.slug]))
        self.assertFalse(first_response.context["can_review"])

        make_booking(user=user, center=center, status=Booking.STATUS_DONE)
        second_response = self.client.get(reverse("services:detail", args=[center.slug]))
        self.assertTrue(second_response.context["can_review"])

    def test_review_create_rejects_user_without_finished_booking(self):
        """Blocheaza postarea unei recenzii daca utilizatorul nu are o programare finalizata la acel service."""
        center = make_service_center(name="No Review Yet")
        user = make_client_user(username="not-eligible")
        self.client.force_login(user)

        response = self.client.post(
            reverse("services:review_create", args=[center.slug]),
            {"rating": 5, "title": "Foarte bun", "body": "Excelent."},
        )

        self.assertRedirects(response, center.get_absolute_url(), fetch_redirect_response=False)
        self.assertFalse(Review.objects.filter(center=center, user=user).exists())

    def test_review_create_saves_review_for_eligible_client(self):
        """Salveaza recenzia atunci cand clientul are deja o programare finalizata la service."""
        center = make_service_center(name="Eligible Review")
        user = make_client_user(username="eligible-review")
        make_booking(user=user, center=center, status=Booking.STATUS_DONE)
        self.client.force_login(user)

        response = self.client.post(
            reverse("services:review_create", args=[center.slug]),
            {
                "rating": 5,
                "title": "Foarte bun",
                "body": "Am fost multumit.",
            },
        )

        self.assertRedirects(response, center.get_absolute_url(), fetch_redirect_response=False)
        review = Review.objects.get(center=center, user=user)
        self.assertEqual(review.rating, 5)

    def test_toggle_favorite_adds_and_removes_service_for_logged_in_user(self):
        """Permite salvarea si eliminarea unui service din favoritele clientului."""
        user = make_client_user(username="fav-user")
        center = make_service_center(name="Favorite Service")
        self.client.force_login(user)

        first = self.client.get(reverse("services:toggle_favorite", args=[center.slug]))
        self.assertEqual(first.status_code, 302)
        self.assertTrue(Favorite.objects.filter(user=user, center=center).exists())

        second = self.client.get(reverse("services:toggle_favorite", args=[center.slug]))
        self.assertEqual(second.status_code, 302)
        self.assertFalse(Favorite.objects.filter(user=user, center=center).exists())
