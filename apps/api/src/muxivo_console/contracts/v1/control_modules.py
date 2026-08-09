from uuid import UUID

from pydantic import BaseModel, Field

from muxivo_console.domain.activity import ModuleCapability, ModuleStatus, Platform


class ControlModuleResponse(BaseModel):
    key: str = Field(examples=["discord.logs"])
    display_name: str = Field(examples=["Audit log"])
    platform: Platform
    capability: ModuleCapability
    status: ModuleStatus


class ControlModuleListResponse(BaseModel):
    organization_id: UUID
    items: list[ControlModuleResponse]
