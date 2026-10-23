import re

from django import forms
from PIL import Image, UnidentifiedImageError


MAX_PHOTO_SIZE = 2 * 1024 * 1024
ALLOWED_PHOTO_FORMATS = {"JPEG", "PNG"}
ALLOWED_PHOTO_CONTENT_TYPES = {"image/jpeg", "image/png"}


def validate_mobile_number(value):
    """Require exactly 10 digits, beginning with 6, 7, 8, or 9."""
    value = (value or "").strip()

    if not re.fullmatch(r"[6-9]\d{9}", value):
        raise forms.ValidationError(
            "Enter a valid 10-digit mobile number starting with 6, 7, 8, or 9."
        )

    return value


def validate_permanent_address(value):
    """Require a permanent address between 10 and 250 characters."""
    value = (value or "").strip()

    if not 10 <= len(value) <= 250:
        raise forms.ValidationError(
            "Permanent address must be between 10 and 250 characters."
        )

    return value


def validate_profile_photo(photo):
    """Allow valid JPEG/PNG images up to 2 MB."""
    if not photo:
        return photo

    if photo.size > MAX_PHOTO_SIZE:
        raise forms.ValidationError("Photo must not exceed 2 MB.")

    if getattr(photo, "content_type", None) not in ALLOWED_PHOTO_CONTENT_TYPES:
        raise forms.ValidationError("Photo must be a JPEG or PNG image.")

    try:
        photo.seek(0)
        with Image.open(photo) as image:
            image.verify()
            image_format = image.format

        if image_format not in ALLOWED_PHOTO_FORMATS:
            raise forms.ValidationError("Photo must be a JPEG or PNG image.")

    except (UnidentifiedImageError, OSError, ValueError):
        raise forms.ValidationError("Upload a valid JPEG or PNG image.")
    finally:
        photo.seek(0)

    return photo
