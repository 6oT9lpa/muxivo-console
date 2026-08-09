from pydantic import BaseModel

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.health import HealthStatus


class HealthSignalResponse(BaseModel):
    key: str
    display_name: str
    value: str
    status: HealthStatus
    latency_ms: int | None


class PlatformHealthResponse(BaseModel):
    organization_id: str
    platform: Platform
    signals: list[HealthSignalResponse]
