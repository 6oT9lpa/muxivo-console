"""Application service that resolves Console authorization from memberships."""

from dataclasses import dataclass

from muxivo_console.application.ports import OrganizationMembershipReader
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest


@dataclass(slots=True)
class MembershipOrganizationAuthorizer:
    """Fail-closed authorizer backed only by Console-owned memberships."""

    memberships: OrganizationMembershipReader

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        membership = await self.memberships.get_membership(
            actor_id=request.actor_id, organization_id=request.organization_id
        )
        if membership is None:
            return AuthorizationDecision.deny()
        return AuthorizationDecision(allowed=membership.allows(request))
