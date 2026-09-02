"""Development organization authorizer that denies by default."""

from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest


class DenyByDefaultOrganizationAuthorizer:
    """Keep development access closed until an explicit adapter is wired."""

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        return AuthorizationDecision.deny()
