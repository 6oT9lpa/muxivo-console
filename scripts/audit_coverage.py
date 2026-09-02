"""Verify that sensitive Console Foundation actions keep audit coverage.

The goal is deliberately practical: every action listed here must have a
production code marker and a regression-test marker. Dynamic actions are allowed
when the implementation has a stable source marker and tests assert the emitted
literal audit action.
"""

from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
APPLICATION_ROOT = REPOSITORY_ROOT / "apps" / "api" / "src" / "muxivo_console"
TEST_ROOT = REPOSITORY_ROOT / "tests"


@dataclass(frozen=True, slots=True)
class AuditCoverageRequirement:
    action: str
    production_markers: tuple[str, ...]
    test_markers: tuple[str, ...]
    rationale: str


FOUNDATION_AUDIT_REQUIREMENTS: tuple[AuditCoverageRequirement, ...] = (
    AuditCoverageRequirement(
        action="auth.email_password_registration",
        production_markers=("auth.email_password_registration",),
        test_markers=("auth.email_password_registration",),
        rationale="Account creation is a security-sensitive identity lifecycle event.",
    ),
    AuditCoverageRequirement(
        action="auth.session_created",
        production_markers=("auth.session_created",),
        test_markers=("auth.session_created",),
        rationale="Browser session creation must remain observable.",
    ),
    AuditCoverageRequirement(
        action="auth.session_reauthenticated",
        production_markers=("auth.session_reauthenticated",),
        test_markers=("auth.session_reauthenticated",),
        rationale="Recent-authentication refresh is a security-sensitive session event.",
    ),
    AuditCoverageRequirement(
        action="auth.session_revoked",
        production_markers=("auth.session_revoked",),
        test_markers=("auth.session_revoked",),
        rationale="Current-session revocation is a security control.",
    ),
    AuditCoverageRequirement(
        action="auth.sessions_revoked",
        production_markers=("auth.sessions_revoked",),
        test_markers=("auth.sessions_revoked",),
        rationale="Bulk session revocation is a security-sensitive destructive action.",
    ),
    AuditCoverageRequirement(
        action="auth.password_changed",
        production_markers=("auth.password_changed",),
        test_markers=("auth.password_changed",),
        rationale="Authenticated password rotation must be audit-visible.",
    ),
    AuditCoverageRequirement(
        action="auth.password_recovery_requested",
        production_markers=("auth.password_recovery_requested",),
        test_markers=("auth.password_recovery_requested",),
        rationale="Recovery requests are abuse-prone and must be traceable without enumeration.",
    ),
    AuditCoverageRequirement(
        action="auth.password_recovered",
        production_markers=("auth.password_recovered",),
        test_markers=("auth.password_recovered",),
        rationale="Recovery completion rotates credentials and revokes sessions.",
    ),
    AuditCoverageRequirement(
        action="identity.link_started",
        production_markers=("identity.link_started",),
        test_markers=("identity.link_started",),
        rationale="External identity link attempts must be visible.",
    ),
    AuditCoverageRequirement(
        action="identity.link",
        production_markers=("identity.link",),
        test_markers=("identity.link",),
        rationale="External identity attachment changes account recovery/login surface.",
    ),
    AuditCoverageRequirement(
        action="identity.unlink",
        production_markers=("identity.unlink",),
        test_markers=("identity.unlink",),
        rationale="Identity removal can reduce usable sign-in methods.",
    ),
    AuditCoverageRequirement(
        action="organization.create",
        production_markers=("organization.create",),
        test_markers=("organization.create",),
        rationale="Organization creation defines the tenant boundary.",
    ),
    AuditCoverageRequirement(
        action="organization.member.add",
        production_markers=("organization.member.add",),
        test_markers=("organization.member.add",),
        rationale="Membership grants organization access.",
    ),
    AuditCoverageRequirement(
        action="organization.member.update",
        production_markers=("organization.member.update",),
        test_markers=("organization.member.update",),
        rationale="Role and scope changes alter authorization.",
    ),
    AuditCoverageRequirement(
        action="organization.member.remove",
        production_markers=("organization.member.remove",),
        test_markers=("organization.member.remove",),
        rationale="Membership removal revokes organization access.",
    ),
    AuditCoverageRequirement(
        action="platform_connection.register",
        production_markers=("platform_connection.register",),
        test_markers=("platform_connection.register",),
        rationale="Platform resource registration crosses the ownership boundary.",
    ),
    AuditCoverageRequirement(
        action="platform_connection.reauthorize",
        production_markers=("PlatformConnectionLifecycleAction.REAUTHORIZE", "audit_action"),
        test_markers=("platform_connection.reauthorize",),
        rationale="Reauthorization restores a previously unsafe connection.",
    ),
    AuditCoverageRequirement(
        action="platform_connection.revoke",
        production_markers=("PlatformConnectionLifecycleAction.REVOKE", "audit_action"),
        test_markers=("platform_connection.revoke",),
        rationale="Revocation intentionally makes a connection unusable.",
    ),
    AuditCoverageRequirement(
        action="platform_connection.disconnect",
        production_markers=("PlatformConnectionLifecycleAction.DISCONNECT", "audit_action"),
        test_markers=("platform_connection.disconnect",),
        rationale="Disconnect is a destructive lifecycle transition.",
    ),
    AuditCoverageRequirement(
        action="platform_connection.reconciled",
        production_markers=("platform_connection.reconciled",),
        test_markers=("platform_connection.reconciled",),
        rationale=(
            "Periodic reconciliation changes connection health state without a browser actor."
        ),
    ),
    AuditCoverageRequirement(
        action="platform_ai_moderation_policy.updated",
        production_markers=("platform_ai_moderation_policy.updated",),
        test_markers=("platform_ai_moderation_policy.updated",),
        rationale="Console-originated platform write commands must be attributable.",
    ),
)


def main() -> int:
    production_source = _read_tree(APPLICATION_ROOT)
    test_source = _read_tree(TEST_ROOT)
    missing: list[str] = []
    for requirement in FOUNDATION_AUDIT_REQUIREMENTS:
        if not all(marker in production_source for marker in requirement.production_markers):
            missing.append(
                f"{requirement.action}: missing production marker(s) "
                f"{requirement.production_markers!r}"
            )
        if not all(marker in test_source for marker in requirement.test_markers):
            missing.append(
                f"{requirement.action}: missing test marker(s) {requirement.test_markers!r}"
            )
    if missing:
        print("Audit coverage review failed:")
        for item in missing:
            print(f"- {item}")
        return 1
    print(
        "Audit coverage review passed: "
        f"{len(FOUNDATION_AUDIT_REQUIREMENTS)} sensitive actions covered."
    )
    return 0


def _read_tree(root: Path) -> str:
    chunks: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


if __name__ == "__main__":
    raise SystemExit(main())
