from typing import Literal

from pydantic import BaseModel, EmailStr


class CreateOrganizationRequest(BaseModel):
    name: str
    slug: str
    branding_name: str | None = None
    support_email: str | None = None


class CreateProjectRequest(BaseModel):
    organization_id: str
    name: str
    slug: str


class CreateEnvironmentRequest(BaseModel):
    project_id: str
    name: str
    slug: str
    kind: Literal["dev", "staging", "preview", "internal"]
    public_hostname: str
    upstream_hostname: str | None = None
    cloudflare_tunnel_id: str | None = None
    cloudflare_access_app_id: str | None = None
    service_token_ref: str | None = None
    requires_app_auth: bool = False


class CreateAccessGrantRequest(BaseModel):
    email: EmailStr
    organization_id: str
    role: Literal["client_member", "reviewer", "agency_admin"]
    display_name: str | None = None


class AuditEventResponse(BaseModel):
    id: str
    actor_user_id: str | None
    event_type: str
    target_type: str | None
    target_id: str | None
    metadata_json: dict | None
    created_at: str


class StatsResponse(BaseModel):
    active_orgs: int
    active_envs: int
    active_users: int
    events_today: int


class StoreServiceTokenRequest(BaseModel):
    client_id: str
    client_secret: str
