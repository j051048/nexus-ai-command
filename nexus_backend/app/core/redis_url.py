"""Redis URL normalization shared by every Redis-backed subsystem.

``redis.from_url()`` validates the scheme while *constructing* the client, so
a malformed ``REDIS_URL`` escapes the connection-handling ``try`` blocks and
turns a degradable dependency into a crash.  In production that surfaced as::

    WARNING [app.agent.stream_checks:72] [Stream] Token budget check failed
        (non-blocking): Redis URL must specify one of the following schemes
        (redis://, rediss://, unix://)

managed Redis providers hand out either a full URL or a bare ``host:port``
pair, and operators regularly paste one where the other is expected.  Rather
than pushing that validation into ~15 call sites, every caller normalizes
through here and degrades deliberately when the answer is ``None``.
"""

from __future__ import annotations

import re

#: Schemes ``redis-py`` accepts.
VALID_REDIS_SCHEMES = ("redis", "rediss", "unix")

_SCHEME_RE = re.compile(r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*)://")

# ``host[:port][/db]`` or ``user:password@host[:port][/db]`` - the shape a
# cloud dashboard shows when it does not hand out a full URL.
_BARE_TARGET_RE = re.compile(
    r"^(?:(?P<userinfo>[^:@/\s]+(?::[^@/\s]*)?)@)?"
    r"(?P<host>[A-Za-z0-9_.\-]+)"
    r"(?::(?P<port>\d{1,5}))?"
    r"(?P<path>/[A-Za-z0-9_.\-]*)?$"
)


def _strip_wrapping_quotes(value: str) -> str:
    """Drop quotes pasted in from a dashboard or ``.env`` snippet.

    ``REDIS_URL="redis://..."`` reaches the process with the quotes intact on
    several PaaS providers, which makes ``urlparse`` report an empty scheme.
    """
    while len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value


def redact_redis_url(raw: str | None) -> str:
    """Return a log-safe rendering of ``raw`` with any password removed."""
    if not isinstance(raw, str):
        return "<unset>"
    value = _strip_wrapping_quotes(raw.strip())
    if not value:
        return "<empty>"
    if "@" not in value:
        return value
    prefix, _, tail = value.rpartition("@")
    scheme = ""
    if "://" in prefix:
        scheme = prefix.split("://", 1)[0] + "://"
        prefix = prefix.split("://", 1)[1]
    user = prefix.split(":", 1)[0]
    return f"{scheme}{user}:***@{tail}"


def normalize_redis_url(raw: str | None) -> str | None:
    """Return a redis-py compatible URL, or ``None`` when unusable.

    ``redis://`` / ``rediss://`` / ``unix://`` pass through untouched.  A bare
    ``host:port`` target gains the ``redis://`` prefix, because that is what
    the operator meant.  Anything else - including ``http(s)://`` URLs copied
    from a different service - is rejected so the caller can degrade.
    """
    if not isinstance(raw, str):
        return None
    value = _strip_wrapping_quotes(raw.strip())
    if not value:
        return None

    match = _SCHEME_RE.match(value)
    if match:
        if match.group("scheme").lower() in VALID_REDIS_SCHEMES:
            return value
        return None

    if any(char.isspace() for char in value):
        return None

    if _BARE_TARGET_RE.match(value):
        return f"redis://{value}"

    return None


def describe_redis_url_problem(raw: str | None) -> str | None:
    """Explain why :func:`normalize_redis_url` rejected a value.

    Returns ``None`` when the value is usable.  The message never contains
    credentials, so it is safe to write to logs and health output.
    """
    if normalize_redis_url(raw) is not None:
        return None

    value = raw.strip() if isinstance(raw, str) else ""
    if not value:
        return "REDIS_URL is not set"

    match = _SCHEME_RE.match(value)
    if match:
        return (
            f"REDIS_URL uses unsupported scheme '{match.group('scheme')}://'; "
            "expected redis://, rediss:// or unix://"
        )
    if any(char.isspace() for char in value):
        return "REDIS_URL contains whitespace"
    return "REDIS_URL is not a valid redis://, rediss:// or unix:// URL"
