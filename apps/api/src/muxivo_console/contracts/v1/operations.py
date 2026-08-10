from typing import Literal

from pydantic import BaseModel

ReadinessStatusResponse = Literal["ready", "unavailable"]


class ReadinessComponentResponse(BaseModel):
    name: str
    status: ReadinessStatusResponse


class ReadinessResponse(BaseModel):
    status: ReadinessStatusResponse
    components: list[ReadinessComponentResponse]
