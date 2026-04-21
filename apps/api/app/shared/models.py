"""
Modèles de données SQLAlchemy — domaine DevGate
Le schéma suit le domaine, pas les écrans.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


# ── User ─────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # client | agency
    status: Mapped[str] = mapped_column(String, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    challenges: Mapped[list["LoginChallenge"]] = relationship(back_populates="user")
    grants: Mapped[list["AccessGrant"]] = relationship(back_populates="user")


# ── Organization ─────────────────────────────────────────────────

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    branding_name: Mapped[str | None] = mapped_column(String)
    logo_url: Mapped[str | None] = mapped_column(String)
    primary_color: Mapped[str | None] = mapped_column(String)
    support_email: Mapped[str | None] = mapped_column(String)

    projects: Mapped[list["Project"]] = relationship(back_populates="organization")
    grants: Mapped[list["AccessGrant"]] = relationship(back_populates="organization")


# ── Project ───────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")
    description: Mapped[str | None] = mapped_column(Text)

    organization: Mapped["Organization"] = relationship(back_populates="projects")
    environments: Mapped[list["Environment"]] = relationship(back_populates="project")


# ── Environment ───────────────────────────────────────────────────

class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # dev|staging|preview|internal
    public_hostname: Mapped[str] = mapped_column(String, nullable=False)

    # Transport Cloudflare — jamais exposé au frontend
    upstream_hostname: Mapped[str | None] = mapped_column(String)
    cloudflare_tunnel_id: Mapped[str | None] = mapped_column(String)
    cloudflare_access_app_id: Mapped[str | None] = mapped_column(String)
    service_token_ref: Mapped[str | None] = mapped_column(String)  # référence au secret store

    requires_app_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="environments")
    health_snapshots: Mapped[list["TunnelHealthSnapshot"]] = relationship(back_populates="environment")

    # Cloudflare — colonnes de provisioning
    discovered_tunnel_id: Mapped[str | None] = mapped_column(ForeignKey("discovered_tunnels.id"))
    provisioning_status: Mapped[str] = mapped_column(String, default="pending")
    # provisioning_status : pending | provisioning | active | failed

    provisioning_jobs: Mapped[list["ProvisioningJob"]] = relationship(back_populates="environment")


# ── AccessGrant ───────────────────────────────────────────────────

class AccessGrant(Base):
    __tablename__ = "access_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_grant_user_org"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # client_member|reviewer|agency_admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="grants")
    organization: Mapped["Organization"] = relationship(back_populates="grants")


# ── Session ───────────────────────────────────────────────────────

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip: Mapped[str | None] = mapped_column(String)
    user_agent: Mapped[str | None] = mapped_column(String)

    user: Mapped["User"] = relationship(back_populates="sessions")


# ── LoginChallenge ────────────────────────────────────────────────

class LoginChallenge(Base):
    __tablename__ = "login_challenges"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # magic_link | otp
    hashed_token: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="challenges")


# ── AuditEvent ────────────────────────────────────────────────────

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String)
    target_id: Mapped[str | None] = mapped_column(String)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


# ── TunnelHealthSnapshot ──────────────────────────────────────────

class TunnelHealthSnapshot(Base):
    __tablename__ = "tunnel_health_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # online | offline | unknown
    replica_count: Mapped[int] = mapped_column(Integer, default=0)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    environment: Mapped["Environment"] = relationship(back_populates="health_snapshots")


# ── EncryptedSecret ───────────────────────────────────────────────

class EncryptedSecret(Base):
    __tablename__ = "encrypted_secrets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    secret_ref: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    secret_type: Mapped[str] = mapped_column(String, nullable=False)
    owner_type: Mapped[str | None] = mapped_column(String)
    owner_id: Mapped[str | None] = mapped_column(String)
    key_id: Mapped[str] = mapped_column(String, nullable=False, default="v1")
    # ciphertext contient le tag GCM en suffixe (format natif cryptography.AESGCM)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)   # base64
    nonce: Mapped[str] = mapped_column(String, nullable=False)       # base64, 12 bytes
    algorithm: Mapped[str] = mapped_column(String, nullable=False, default="AES-256-GCM")
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ── DiscoveredTunnel ──────────────────────────────────────────────

class DiscoveredTunnel(Base):
    __tablename__ = "discovered_tunnels"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    cloudflare_tunnel_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="discovered")
    # status : discovered | assigned | orphaned
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── ProvisioningJob ───────────────────────────────────────────────

class ProvisioningJob(Base):
    __tablename__ = "provisioning_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="cloudflare")
    state: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    # states : pending|creating_access_app|access_app_created|creating_policy|policy_created|
    #          creating_service_token|service_token_created_unsealed|secret_persisted|
    #          creating_dns|active|failed_recoverable|failed_terminal|compensating|rolled_back
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    cloudflare_access_app_id: Mapped[str | None] = mapped_column(String)
    cloudflare_policy_id: Mapped[str | None] = mapped_column(String)
    cloudflare_service_token_id: Mapped[str | None] = mapped_column(String)
    dns_record_id: Mapped[str | None] = mapped_column(String)
    secret_persisted: Mapped[bool] = mapped_column(Boolean, default=False)
    dns_published: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    environment: Mapped["Environment"] = relationship(back_populates="provisioning_jobs")
