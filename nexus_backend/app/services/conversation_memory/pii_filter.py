"""PII filter for memory storage — sanitize sensitive data before persisting.

Strips or masks personally identifiable information (PII) from memory text
to comply with data protection regulations (GDPR / PIPL).
"""

import re

# ── Patterns ───────────────────────────────────────────────────────

# China mobile: 1[3-9]X XXXX XXXX (exactly 11 digits)
_CHINA_MOBILE = re.compile(
    r"(?<!\d)"
    r"(1[3-9]\d)"  # first 3 digits
    r"(\d{4})"  # middle 4 (masked)
    r"(\d{4})"  # last 4
    r"(?!\d)",
)

# China ID card: 18 digits (last may be X), with birth date validation
# Format: RRRRRRYYYYMMDDSSSC  (R=region, Y=year, M=month, D=day, S=seq, C=check)
_CHINA_ID_CARD = re.compile(
    r"(?<!\d)"
    r"(\d{6})"  # region code
    r"((?:19|20)\d{2}"  # year 19xx/20xx
    r"(?:0[1-9]|1[0-2])"  # month 01-12
    r"(?:0[1-9]|[12]\d|3[01])"  # day 01-31
    r"\d{3})"  # sequence (masked together with date)
    r"([\dXx])"  # check digit
    r"(?!\d)",
)

# Bank card: 16-19 digits, starts with common BINs (4/5/6/9)
_BANK_CARD = re.compile(
    r"(?<!\d)"
    r"([4-6]\d{3}|9\d{3})"  # first 4 digits (BIN: Visa 4, MC 5, UnionPay 6, etc.)
    r"(\d{8,11})"  # middle digits (masked)
    r"(\d{4})"  # last 4
    r"(?!\d)",
)

_EMAIL = re.compile(
    r"([a-zA-Z0-9._%+-]+)" r"@" r"([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
)

_PASSPORT = re.compile(
    r"(?<![A-Za-z\d])" r"([A-Z]{1,2})" r"(\d{7,8})" r"(?!\d)",
)


def _mask_mobile(m: re.Match) -> str:
    return f"{m.group(1)}****{m.group(3)}"


def _mask_id_card(m: re.Match) -> str:
    return f"{m.group(1)}{'*' * len(m.group(2))}{m.group(3)}"


def _mask_bank_card(m: re.Match) -> str:
    return f"{m.group(1)}{'*' * len(m.group(2))}{m.group(3)}"


def _mask_email(m: re.Match) -> str:
    local = m.group(1)
    domain = m.group(2)
    if len(local) <= 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***@{domain}"


def _mask_passport(m: re.Match) -> str:
    return f"{m.group(1)}{'*' * len(m.group(2))}"


# Ordered: most specific first to avoid partial matches
_PIPELINE: list[tuple[re.Pattern, callable]] = [
    (_CHINA_ID_CARD, _mask_id_card),  # 18-digit ID card (before bank card)
    (_BANK_CARD, _mask_bank_card),  # 16-19 digit bank card
    (_CHINA_MOBILE, _mask_mobile),  # 11-digit mobile
    (_EMAIL, _mask_email),
    (_PASSPORT, _mask_passport),
]


def sanitize_pii(text: str) -> str:
    """Replace PII patterns in *text* with masked versions.

    Returns the sanitized string. If no PII is found, returns the
    original string unchanged.
    """
    if not text:
        return text

    result = text
    for pattern, replacer in _PIPELINE:
        result = pattern.sub(replacer, result)
    return result


# 别名以保持向后兼容
mask_pii = sanitize_pii
mask_pii_for_storage = sanitize_pii
