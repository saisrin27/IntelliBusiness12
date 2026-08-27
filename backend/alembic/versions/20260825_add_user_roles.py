"""Add user roles and promote the fixed administrator account.

Revision ID: 20260825_add_user_roles
Revises:
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_add_user_roles"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "role" not in columns:
        op.add_column("users", sa.Column("role", sa.String(length=50), nullable=False, server_default="user"))
    op.execute(
        sa.text(
            "UPDATE users SET role = 'admin' "
            "WHERE LOWER(email) = 'intellibusiness12@gmail.com'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "role" in columns:
        op.drop_column("users", "role")
