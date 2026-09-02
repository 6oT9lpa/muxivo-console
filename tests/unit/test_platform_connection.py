from uuid import uuid4

import pytest
from muxivo_console.domain.activity import Platform
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
