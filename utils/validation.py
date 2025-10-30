"""
Input validation functions for XP Bot
"""
import re
from zoneinfo import ZoneInfo

# Validation constants
MAX_CHARACTER_NAME_LENGTH = 100
MIN_CHARACTER_NAME_LENGTH = 1
MAX_XP_GRANT = 1000000  # 1 million max XP per grant
MIN_XP_GRANT = -100000  # Allow removing up to 100k XP
MAX_DAILY_CAP = 1000
MIN_DAILY_CAP = 1
MAX_CHAR_PER_RP = 10000
MIN_CHAR_PER_RP = 1


def validate_character_name(name: str) -> tuple[bool, str]:
    """
    Validate character name.
    Returns (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Character name cannot be empty."

    name = name.strip()

    if len(name) < MIN_CHARACTER_NAME_LENGTH:
        return False, f"Character name must be at least {MIN_CHARACTER_NAME_LENGTH} character."

    if len(name) > MAX_CHARACTER_NAME_LENGTH:
        return False, f"Character name cannot exceed {MAX_CHARACTER_NAME_LENGTH} characters."

    # Check for valid characters (alphanumeric, spaces, basic punctuation)
    if not re.match(r'^[a-zA-Z0-9\s\-\'\.]+$', name):
        return False, "Character name can only contain letters, numbers, spaces, hyphens, apostrophes, and periods."

    return True, ""


def validate_xp_amount(amount: int, allow_negative: bool = False) -> tuple[bool, str]:
    """
    Validate XP amount.
    Returns (is_valid, error_message)
    """
    if not allow_negative and amount < 0:
        return False, "XP amount cannot be negative."

    if amount < MIN_XP_GRANT:
        return False, f"XP amount cannot be less than {MIN_XP_GRANT}."

    if amount > MAX_XP_GRANT:
        return False, f"XP amount cannot exceed {MAX_XP_GRANT:,}."

    return True, ""


def validate_daily_cap(cap: int) -> tuple[bool, str]:
    """
    Validate daily cap value.
    Returns (is_valid, error_message)
    """
    if cap < MIN_DAILY_CAP:
        return False, f"Daily cap must be at least {MIN_DAILY_CAP}."

    if cap > MAX_DAILY_CAP:
        return False, f"Daily cap cannot exceed {MAX_DAILY_CAP}."

    return True, ""


def validate_char_per_rp(amount: int) -> tuple[bool, str]:
    """
    Validate characters per RP XP value.
    Returns (is_valid, error_message)
    """
    if amount < MIN_CHAR_PER_RP:
        return False, f"Characters per XP must be at least {MIN_CHAR_PER_RP}."

    if amount > MAX_CHAR_PER_RP:
        return False, f"Characters per XP cannot exceed {MAX_CHAR_PER_RP}."

    return True, ""


def validate_timezone(tz_string: str) -> tuple[bool, str]:
    """
    Validate timezone string.
    Returns (is_valid, error_message)
    """
    try:
        ZoneInfo(tz_string)
        return True, ""
    except Exception:
        return False, f"Invalid timezone '{tz_string}'. Use format like 'America/New_York' or 'UTC'."


def validate_image_url(url: str) -> tuple[bool, str]:
    """
    Validate image URL (basic validation).
    Returns (is_valid, error_message)
    """
    if not url:
        return True, ""  # Optional field

    # Basic URL pattern
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(url):
        return False, "Invalid URL format. Must start with http:// or https://"

    if len(url) > 2000:
        return False, "URL is too long (max 2000 characters)."

    return True, ""


def validate_character_sheet_url(url: str) -> tuple[bool, str]:
    """
    Validate character sheet URL (basic validation).
    Returns (is_valid, error_message)
    """
    if not url:
        return True, ""  # Optional field

    # Use the same URL validation pattern
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(url):
        return False, "Invalid URL format. Must start with http:// or https://"

    if len(url) > 2000:
        return False, "URL is too long (max 2000 characters)."

    return True, ""
