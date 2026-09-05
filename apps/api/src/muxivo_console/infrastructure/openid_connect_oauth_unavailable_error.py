"""Failure raised when an OIDC provider cannot be verified safely."""


class OpenIdConnectOAuthUnavailableError(RuntimeError):
    """Keep provider HTTP and payload details out of application responses."""
