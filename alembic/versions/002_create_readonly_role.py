"""Create marketmind_readonly role

Automates what scripts/create_readonly_roles.sql documented as a manual,
one-time step per fresh database (see marketmind-core README
"Conectividade entre serviços") — marketmind-core reads this service's
tables directly over its host-exposed Postgres port using this role.
Idempotent (checks pg_roles before creating), safe to run on every
migration pass, not just a fresh volume. Password must match
OECD_DB_PASSWORD in marketmind-core's .env.

Revision ID: 002
Revises: 001
Create Date: 2026-07-08

"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'marketmind_readonly') THEN
                CREATE ROLE marketmind_readonly WITH LOGIN PASSWORD 'admin';
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO marketmind_readonly;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO marketmind_readonly;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO marketmind_readonly;")


def downgrade() -> None:
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM marketmind_readonly;")
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM marketmind_readonly;")
    op.execute("REVOKE USAGE ON SCHEMA public FROM marketmind_readonly;")
    op.execute("DROP ROLE IF EXISTS marketmind_readonly;")
