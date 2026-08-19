import pytest
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.role_purposes import PlatformRolePurposes, RolePurpose


def test_accepts_platform_role_assignments() -> None:
    assignments = PlatformRolePurposes(
        Platform.DISCORD, {RolePurpose.ACTIVITY_ADMIN: "123"}
    )

    assert assignments.assignments[RolePurpose.ACTIVITY_ADMIN] == "123"


def test_rejects_blank_role_assignment() -> None:
    with pytest.raises(ValueError, match="non-empty role IDs"):
        PlatformRolePurposes(Platform.DISCORD, {RolePurpose.PING_DEV: ""})
