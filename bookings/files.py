from mimetypes import guess_type


def build_attachment_summary(*, actor_label, count, image_count=0, video_count=0):
    if count <= 0:
        return ""
    if image_count == count:
        noun = "poza" if count == 1 else "poze"
    elif video_count == count:
        noun = "video" if count == 1 else "video-uri"
    else:
        noun = "fisier" if count == 1 else "fisiere"
    return f"{actor_label} a adaugat {count} {noun}."


def sanitize_uploaded_filename(name):
    cleaned = str(name or "").replace("\x00", "").strip()
    if not cleaned:
        return "fisier"
    normalized = cleaned.replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1].strip()
    return basename or "fisier"


def prepare_uploaded_file(uploaded_file):
    if uploaded_file is None:
        return uploaded_file
    uploaded_file.name = sanitize_uploaded_filename(getattr(uploaded_file, "name", ""))
    return uploaded_file


def attachment_display_name(attachment):
    return sanitize_uploaded_filename(getattr(getattr(attachment, "file", None), "name", ""))


def attachment_content_type(attachment):
    filename = attachment_display_name(attachment)
    guessed_type, _ = guess_type(filename)
    if guessed_type:
        return guessed_type
    if getattr(attachment, "media_kind", "") == "video":
        return "video/mp4"
    if getattr(attachment, "media_kind", "") == "image":
        return "image/jpeg"
    return "application/octet-stream"
