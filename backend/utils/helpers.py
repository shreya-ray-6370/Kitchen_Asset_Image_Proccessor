from typing import Tuple

ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"]
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024


def validate_file_type(content_type: str) -> bool:
    return content_type in ALLOWED_TYPES


def validate_file_size(size_in_bytes: int) -> bool:
    return 0 < size_in_bytes <= MAX_FILE_SIZE_BYTES


def validate_upload(content_type: str, size_in_bytes: int) -> Tuple[bool, str]:
    if not validate_file_type(content_type):
        return False, "Unsupported file type. Allowed: image/jpeg, image/png, image/webp"

    if not validate_file_size(size_in_bytes):
        return False, "Invalid file size. Max allowed size is 15MB"

    return True, ""