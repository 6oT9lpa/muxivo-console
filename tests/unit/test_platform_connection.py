from uuid import uuid4

import pytest
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.connection_reconciliation import (
    ConnectionReconciliationDecision,
    ConnectionReconciliationReason,
)
from muxivo_console.domain.connection_status_reason import ConnectionStatusReason
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection


def connection(status: ConnectionStatus) -> PlatformConnection:
    return PlatformConnection(
        id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123456789012345678",
        status=status,
    )


@pytest.mark.parametrize(
    ("current", "target"),
    (
        (ConnectionStatus.PENDING, ConnectionStatus.ACTIVE),
        (ConnectionStatus.PENDING, ConnectionStatus.DEGRADED),
        (ConnectionStatus.ACTIVE, ConnectionStatus.DEGRADED),
        (ConnectionStatus.DEGRADED, ConnectionStatus.ACTIVE),
        (ConnectionStatus.ACTIVE, ConnectionStatus.REAUTH_REQUIRED),
        (ConnectionStatus.REAUTH_REQUIRED, ConnectionStatus.ACTIVE),
        (ConnectionStatus.REAUTH_REQUIRED, ConnectionStatus.DISCONNECTED),
    ),
)
def test_allows_only_documented_lifecycle_transitions(
    current: ConnectionStatus, target: ConnectionStatus
) -> None:
    transitioned = connection(current).transition_to(target)

    assert transitioned.status is target


@pytest.mark.parametrize(
    ("current", "target"),
    (
        (ConnectionStatus.ACTIVE, ConnectionStatus.PENDING),
        (ConnectionStatus.DISCONNECTED, ConnectionStatus.ACTIVE),
        (ConnectionStatus.DISCONNECTED, ConnectionStatus.REAUTH_REQUIRED),
    ),
)
def test_rejects_unsafe_or_irreversible_lifecycle_transitions(
    current: ConnectionStatus, target: ConnectionStatus
) -> None:
    with pytest.raises(ValueError, match="Cannot transition connection"):
        connection(current).transition_to(target)


def test_rejects_blank_external_resource_identifier() -> None:
    with pytest.raises(ValueError, match="External resource identifier"):
        PlatformConnection(
            id=uuid4(),
            organization_id=uuid4(),
            platform=Platform.TWITCH,
            external_resource_id=" ",
            status=ConnectionStatus.PENDING,
        )


def test_transition_preserves_a_typed_reason_for_browser_explanation() -> None:
    transitioned = connection(ConnectionStatus.PENDING).transition_to(
        ConnectionStatus.DEGRADED,
        reason=ConnectionStatusReason.PREFLIGHT_FAILED,
    )

    assert transitioned.status_reason is ConnectionStatusReason.PREFLIGHT_FAILED


def test_rejects_an_untyped_connection_status_reason() -> None:
    with pytest.raises(ValueError, match="Connection status reason"):
        PlatformConnection(
            id=uuid4(),
            organization_id=uuid4(),
            platform=Platform.TWITCH,
            external_resource_id="channel-1",
            status=ConnectionStatus.DEGRADED,
            status_reason="provider leaked detail",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("target_status", "reason"),
    (
        (ConnectionStatus.ACTIVE, ConnectionReconciliationReason.TOKEN_EXPIRED),
        (ConnectionStatus.DEGRADED, ConnectionReconciliationReason.SCOPES_MISSING),
        (ConnectionStatus.ACTIVE, ConnectionReconciliationReason.PREFLIGHT_FAILED),
        (ConnectionStatus.DEGRADED, ConnectionReconciliationReason.RESOURCE_REMOVED),
        (ConnectionStatus.REAUTH_REQUIRED, ConnectionReconciliationReason.HEALTHY),
    ),
)
def test_rejects_reconciliation_reason_that_does_not_match_target_status(
    target_status: ConnectionStatus,
    reason: ConnectionReconciliationReason,
) -> None:
    with pytest.raises(ValueError, match="does not match target status"):
        ConnectionReconciliationDecision(target_status=target_status, reason=reason)


def test_allows_preflight_failure_to_remain_pending_or_become_degraded() -> None:
    pending = ConnectionReconciliationDecision(
        target_status=ConnectionStatus.PENDING,
        reason=ConnectionReconciliationReason.PREFLIGHT_FAILED,
    )
    degraded = ConnectionReconciliationDecision(
        target_status=ConnectionStatus.DEGRADED,
        reason=ConnectionReconciliationReason.PREFLIGHT_FAILED,
    )

    assert pending.target_status is ConnectionStatus.PENDING
    assert degraded.target_status is ConnectionStatus.DEGRADED
