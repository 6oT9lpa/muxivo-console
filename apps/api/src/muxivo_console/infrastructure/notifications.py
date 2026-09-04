"""Compatibility exports for focused notification adapters.

Each notifier implementation lives in its own module. Existing imports remain
valid while composition roots can depend on the focused modules directly.
"""

from muxivo_console.infrastructure.smtp_email_password_registration_verification_notifier import (
    SmtpEmailPasswordRegistrationVerificationNotifier,
)
from muxivo_console.infrastructure.smtp_organization_invitation_notifier import (
    SmtpOrganizationInvitationNotifier,
)
from muxivo_console.infrastructure.smtp_password_recovery_completion_notifier import (
    SmtpPasswordRecoveryCompletionNotifier,
)
from muxivo_console.infrastructure.smtp_password_recovery_notifier import (
    SmtpPasswordRecoveryNotifier,
)
from muxivo_console.infrastructure.undelivered_organization_invitation_notifier import (
    UndeliveredOrganizationInvitationNotifier,
)
from muxivo_console.infrastructure.undelivered_password_recovery_completion_notifier import (
    UndeliveredPasswordRecoveryCompletionNotifier,
)
from muxivo_console.infrastructure.undelivered_password_recovery_notifier import (
    UndeliveredPasswordRecoveryNotifier,
)

from .undelivered_email_password_registration_verification_notifier import (
    UndeliveredEmailPasswordRegistrationVerificationNotifier,
)

__all__ = [
    "SmtpEmailPasswordRegistrationVerificationNotifier",
    "SmtpOrganizationInvitationNotifier",
    "SmtpPasswordRecoveryCompletionNotifier",
    "SmtpPasswordRecoveryNotifier",
    "UndeliveredEmailPasswordRegistrationVerificationNotifier",
    "UndeliveredOrganizationInvitationNotifier",
    "UndeliveredPasswordRecoveryCompletionNotifier",
    "UndeliveredPasswordRecoveryNotifier",
]
