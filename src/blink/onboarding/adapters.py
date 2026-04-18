"""OTP delivery adapters.

Keeps the service layer ignorant of *how* an OTP reaches the parent.
Dev-mode adapter logs to stdout; production adapters will be swapped in
for email (SES/Postmark) and SMS (Twilio/Sinch) in a later sprint.
"""
from __future__ import annotations

import logging
from typing import Protocol


log = logging.getLogger("blink.onboarding.otp")


class OtpDeliveryAdapter(Protocol):
    """Contract: deliver a 6-digit OTP to a contact endpoint.

    Implementations must NOT store the OTP anywhere. The backend keeps a
    hash in the DB; the plaintext only exists in-flight to the adapter.
    """

    async def send_otp(
        self,
        *,
        contact: str,
        otp: str,
        invite_token: str,
        child_display_name: str | None = None,
    ) -> None: ...


class ConsoleOtpAdapter:
    """Dev adapter. Prints to stdout AND to the structured log.

    Use only when BLINK_ENV=dev. Production envs must refuse to start if
    this is wired.
    """

    async def send_otp(
        self,
        *,
        contact: str,
        otp: str,
        invite_token: str,
        child_display_name: str | None = None,
    ) -> None:
        msg = (
            f"[DEV OTP] child={child_display_name or '(unknown)'} "
            f"contact={contact} otp={otp} invite_token={invite_token}"
        )
        # stdout for easy eyeballing in `uvicorn --reload` output
        print(msg)
        # Structured log so it's captured by any shipper too
        log.info(
            "dev_otp_issued",
            extra={
                "blink_contact": contact,
                "blink_otp": otp,
                "blink_invite_token": invite_token,
                "blink_child_name": child_display_name or "",
            },
        )


class NullOtpAdapter:
    """Never sends. Used in tests where the code is read directly from the DB
    or returned by the service. Fast + no stdout noise."""

    async def send_otp(
        self,
        *,
        contact: str,
        otp: str,
        invite_token: str,
        child_display_name: str | None = None,
    ) -> None:
        return None
