"""Configuration validation error for the production composition root."""


class ConfigurationError(ValueError):
    """Raised before serving traffic when a required setting is unsafe."""
