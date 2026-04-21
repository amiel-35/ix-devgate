"""cloudflare provisioning + encrypted secrets

Revision ID: b2c4e6f8a012
Revises: abe783e8a216
Create Date: 2026-04-21 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c4e6f8a012"
down_revision: Union[str, None] = "abe783e8a216"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── encrypted_secrets ─────────────────────────────────────────
    op.create_table(
        "encrypted_secrets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("secret_ref", sa.String(), nullable=False),
        sa.Column("secret_type", sa.String(), nullable=False),
        sa.Column("owner_type", sa.String(), nullable=True),
        sa.Column("owner_id", sa.String(), nullable=True),
        sa.Column("key_id", sa.String(), nullable=False, server_default="v1"),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("algorithm", sa.String(), nullable=False, server_default="AES-256-GCM"),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret_ref"),
    )
    op.create_index("ix_encrypted_secrets_secret_ref", "encrypted_secrets", ["secret_ref"], unique=True)

    # ── discovered_tunnels ────────────────────────────────────────
    op.create_table(
        "discovered_tunnels",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("cloudflare_tunnel_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="discovered"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cloudflare_tunnel_id"),
    )
    op.create_index("ix_discovered_tunnels_cf_id", "discovered_tunnels", ["cloudflare_tunnel_id"], unique=True)

    # ── provisioning_jobs ─────────────────────────────────────────
    op.create_table(
        "provisioning_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("environment_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="cloudflare"),
        sa.Column("state", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("cloudflare_access_app_id", sa.String(), nullable=True),
        sa.Column("cloudflare_policy_id", sa.String(), nullable=True),
        sa.Column("cloudflare_service_token_id", sa.String(), nullable=True),
        sa.Column("dns_record_id", sa.String(), nullable=True),
        sa.Column("secret_persisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dns_published", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provisioning_jobs_env_id", "provisioning_jobs", ["environment_id"], unique=False)

    # ── environments — nouvelles colonnes ─────────────────────────
    op.add_column("environments", sa.Column("discovered_tunnel_id", sa.String(), nullable=True))
    op.add_column("environments", sa.Column("provisioning_status", sa.String(), nullable=False, server_default="pending"))
    op.create_foreign_key(
        "fk_environments_discovered_tunnel",
        "environments", "discovered_tunnels",
        ["discovered_tunnel_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_environments_discovered_tunnel", "environments", type_="foreignkey")
    op.drop_column("environments", "provisioning_status")
    op.drop_column("environments", "discovered_tunnel_id")
    op.drop_index("ix_provisioning_jobs_env_id", table_name="provisioning_jobs")
    op.drop_table("provisioning_jobs")
    op.drop_index("ix_discovered_tunnels_cf_id", table_name="discovered_tunnels")
    op.drop_table("discovered_tunnels")
    op.drop_index("ix_encrypted_secrets_secret_ref", table_name="encrypted_secrets")
    op.drop_table("encrypted_secrets")
