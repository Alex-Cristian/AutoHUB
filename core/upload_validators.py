from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError


DEFAULT_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt"}
DEFAULT_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}


def max_upload_size_bytes(megabytes: int) -> int:
    return int(megabytes) * 1024 * 1024


def validate_uploaded_file(
    uploaded_file,
    *,
    allowed_extensions,
    allowed_content_types,
    max_size,
    label="Fisierul",
):
    if not uploaded_file:
        return uploaded_file

    name = getattr(uploaded_file, "name", "") or "fisier"
    extension = Path(name).suffix.lower()
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    size = int(getattr(uploaded_file, "size", 0) or 0)

    if extension not in {ext.lower() for ext in allowed_extensions}:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(f"{label} {name} nu are o extensie acceptata. Formate permise: {allowed}.")

    if allowed_content_types and content_type not in {item.lower() for item in allowed_content_types}:
        raise ValidationError(f"{label} {name} nu are un tip de continut acceptat.")

    if size > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValidationError(f"{label} {name} depaseste limita de {max_mb} MB.")

    return uploaded_file


def validate_image_file(uploaded_file, *, max_size=None, label="Imaginea"):
    return validate_uploaded_file(
        uploaded_file,
        allowed_extensions=DEFAULT_IMAGE_EXTENSIONS,
        allowed_content_types={
            "image/jpeg",
            "image/png",
            "image/webp",
        },
        max_size=max_size or max_upload_size_bytes(getattr(settings, "MAX_IMAGE_UPLOAD_MB", 8)),
        label=label,
    )


def validate_document_file(uploaded_file, *, max_size=None, label="Documentul"):
    return validate_uploaded_file(
        uploaded_file,
        allowed_extensions=DEFAULT_DOCUMENT_EXTENSIONS,
        allowed_content_types={
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.oasis.opendocument.text",
            "application/rtf",
            "text/plain",
        },
        max_size=max_size or max_upload_size_bytes(getattr(settings, "MAX_DOCUMENT_UPLOAD_MB", 12)),
        label=label,
    )


def validate_booking_media_file(uploaded_file, *, max_size=None):
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type.startswith("image/"):
        return validate_uploaded_file(
            uploaded_file,
            allowed_extensions=DEFAULT_IMAGE_EXTENSIONS,
            allowed_content_types={"image/jpeg", "image/png", "image/webp"},
            max_size=max_size or max_upload_size_bytes(getattr(settings, "MAX_IMAGE_UPLOAD_MB", 8)),
            label="Fisierul",
        )

    if content_type.startswith("video/"):
        return validate_uploaded_file(
            uploaded_file,
            allowed_extensions=DEFAULT_VIDEO_EXTENSIONS,
            allowed_content_types={
                "video/mp4",
                "video/quicktime",
                "video/webm",
                "video/x-msvideo",
                "video/x-matroska",
            },
            max_size=max_size or max_upload_size_bytes(getattr(settings, "MAX_VIDEO_UPLOAD_MB", 50)),
            label="Fisierul",
        )

    raise ValidationError(f"Fisierul {getattr(uploaded_file, 'name', 'selectat')} trebuie sa fie imagine sau video.")
