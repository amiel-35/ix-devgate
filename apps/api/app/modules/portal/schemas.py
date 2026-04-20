from pydantic import BaseModel


class MeResponse(BaseModel):
    id: str
    email: str
    display_name: str | None


class EnvironmentListItem(BaseModel):
    id: str
    organization_name: str
    project_name: str
    environment_name: str
    kind: str
    url: str
    requires_app_auth: bool
    status: str  # online | offline | unknown


class SessionItem(BaseModel):
    id: str
    expires_at: str
    last_seen_at: str
    ip: str | None
    user_agent: str | None
    is_current: bool
