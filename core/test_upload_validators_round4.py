from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from core.upload_validators import (
    max_upload_size_bytes,
    validate_booking_media_file,
    validate_document_file,
    validate_image_file,
)


class UploadValidatorsRoundFourTests(SimpleTestCase):
    def test_validate_image_file_rejects_invalid_extension(self):
        """Blocheaza imaginile cu extensii periculoase sau neacceptate chiar daca mime-type-ul pare corect."""
        uploaded = SimpleUploadedFile(
            "poza.exe",
            b"fake-image",
            content_type="image/png",
        )

        with self.assertRaisesMessage(ValidationError, "extensie acceptata"):
            validate_image_file(uploaded)

    def test_validate_document_file_rejects_invalid_content_type(self):
        """Refuza documentele care au extensia buna, dar mime-type nepotrivit."""
        uploaded = SimpleUploadedFile(
            "contract.pdf",
            b"%PDF-1.4 fake",
            content_type="image/png",
        )

        with self.assertRaisesMessage(ValidationError, "tip de continut acceptat"):
            validate_document_file(uploaded)

    def test_validate_booking_media_file_accepts_supported_video(self):
        """Permite fisiere video valide pentru atasamentele din booking."""
        uploaded = SimpleUploadedFile(
            "inspectie.mp4",
            b"0" * 1024,
            content_type="video/mp4",
        )

        validated = validate_booking_media_file(uploaded)

        self.assertEqual(validated.name, "inspectie.mp4")

    def test_validate_booking_media_file_rejects_unknown_media_type(self):
        """Respinge orice fisier care nu este imagine sau video in zona media a booking-ului."""
        uploaded = SimpleUploadedFile(
            "script.js",
            b"alert('x')",
            content_type="application/javascript",
        )

        with self.assertRaisesMessage(ValidationError, "trebuie sa fie imagine sau video"):
            validate_booking_media_file(uploaded)

    def test_validate_booking_media_file_rejects_oversized_video(self):
        """Aplica limita de dimensiune pentru video cand se trimite media prea mare."""
        uploaded = SimpleUploadedFile(
            "filmare.mp4",
            b"0" * 16,
            content_type="video/mp4",
        )

        with self.assertRaisesMessage(ValidationError, "depaseste limita de 0 MB"):
            validate_booking_media_file(uploaded, max_size=8)

    def test_validate_image_file_accepts_uppercase_extension_at_exact_limit(self):
        """Accepta imaginea cand extensia este uppercase si dimensiunea este exact limita permisa."""
        uploaded = SimpleUploadedFile(
            "POZA.JPG",
            b"1" * 8,
            content_type="image/jpeg",
        )

        validated = validate_image_file(uploaded, max_size=8)

        self.assertEqual(validated.name, "POZA.JPG")

    def test_validate_document_file_accepts_text_document_at_exact_limit(self):
        """Permite documentele text valide cand dimensiunea este exact cat limita setata."""
        uploaded = SimpleUploadedFile(
            "nota.TXT",
            b"2" * 12,
            content_type="text/plain",
        )

        validated = validate_document_file(uploaded, max_size=12)

        self.assertEqual(validated.name, "nota.TXT")

    def test_max_upload_size_bytes_returns_megabytes_in_bytes(self):
        """Pastreaza conversia corecta MB -> bytes pentru limitele folosite de validatori."""
        self.assertEqual(max_upload_size_bytes(12), 12 * 1024 * 1024)
