"""Seed minimal pour développement local.
Run: python -m app.seeds
"""
from app.database import SessionLocal
from app.shared.models import (
    AccessGrant, Environment, Organization, Project, User,
)


def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("Seed déjà présent, skip.")
            return

        # Admin agence
        admin = User(
            email="admin@agence.fr",
            display_name="Admin Agence",
            kind="agency",
            status="active",
        )
        db.add(admin)
        db.flush()

        # Organization agence + grant admin
        org = Organization(name="Agence", slug="agence", branding_name="Agence")
        db.add(org)
        db.flush()
        db.add(AccessGrant(user_id=admin.id, organization_id=org.id, role="agency_admin"))

        # Client démo
        client_org = Organization(name="Client X", slug="client-x")
        db.add(client_org)
        db.flush()

        project = Project(
            organization_id=client_org.id,
            name="Refonte site",
            slug="refonte-site",
        )
        db.add(project)
        db.flush()

        env = Environment(
            project_id=project.id,
            name="Staging principal",
            slug="staging",
            kind="staging",
            public_hostname="client-x-staging.devgate.local",
            upstream_hostname="example-upstream.cfargotunnel.com",
            requires_app_auth=True,
            status="active",
        )
        db.add(env)

        # User client
        client_user = User(
            email="marie@client-x.com",
            display_name="Marie Chevalier",
            kind="client",
            status="active",
        )
        db.add(client_user)
        db.flush()
        db.add(AccessGrant(user_id=client_user.id, organization_id=client_org.id, role="client_member"))

        db.commit()
        print("✅ Seed créé : admin@agence.fr + marie@client-x.com")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
