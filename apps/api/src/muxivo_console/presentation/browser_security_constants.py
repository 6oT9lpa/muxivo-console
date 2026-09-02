"""Shared browser security constants for the Console presentation layer."""

SESSION_COOKIE_NAME = "__Host-muxivo_session"
CSRF_COOKIE_NAME = "__Host-muxivo_csrf"
DEFAULT_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'"
)
