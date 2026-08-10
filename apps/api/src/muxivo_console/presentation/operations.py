"""Operational probes for deployment orchestrators and load balancers."""

from fastapi import APIRouter, Response, status

from muxivo_console.application.check_readiness import CheckReadiness, ReadinessStatus
from muxivo_console.contracts.v1.operations import (
    ReadinessComponentResponse,
    ReadinessResponse,
)


def create_operations_router(check_readiness: CheckReadiness) -> APIRouter:
    router = APIRouter(tags=["operations"])

    @router.get("/readyz", response_model=ReadinessResponse)
    async def readyz(response: Response) -> ReadinessResponse:
        report = await check_readiness.execute()
        if report.status is ReadinessStatus.UNAVAILABLE:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status=report.status.value,
            components=[
                ReadinessComponentResponse(name=component.name, status=component.status.value)
                for component in report.components
            ],
        )

    return router
