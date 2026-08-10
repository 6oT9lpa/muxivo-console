"""HTTP boundary for first-party browser-session lifecycle operations."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status

from muxivo_console.application.revoke_browser_session import (
    RevokeBrowserSession,
    RevokeBrowserSessionCommand,
)
from muxivo_console.presentation.api import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME


def create_browser_session_router(revoke_session: RevokeBrowserSession) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth/sessions", tags=["authentication"])

    @router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
    async def revoke_current_session(request: Request) -> Response:
        actor_id = getattr(request.state, "actor_id", None)
        session_id = getattr(request.state, "session_id", None)
        if not isinstance(actor_id, UUID) or not isinstance(session_id, UUID):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        await revoke_session.execute(
            RevokeBrowserSessionCommand(
                actor_id=actor_id,
                session_id=session_id,
                correlation_id=request.state.correlation_id,
            )
        )

        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            SESSION_COOKIE_NAME,
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        response.delete_cookie(
            CSRF_COOKIE_NAME,
            path="/",
            secure=True,
            httponly=False,
            samesite="lax",
        )
        return response

    return router
