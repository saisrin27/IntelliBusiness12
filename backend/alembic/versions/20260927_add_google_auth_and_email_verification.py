"""Add Google identity and email verification support.

Revision ID: 20260927_google_email_auth
Revises: 20260825_add_admin_automations
Create Date: 2026-09-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260927_google_email_auth"
down_revision = "20260825_add_admin_automations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"]: column for column in inspector.get_columns("users")}
    if "password_hash" in user_columns and not user_columns["password_hash"]["nullable"]:
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "password_hash",
                existing_type=sa.String(length=255),
                nullable=True,
            )
    for column in ("google_sub", "email_verified"):
        if column not in user_columns:
            with op.batch_alter_table("users") as batch_op:
                if column == "google_sub":
                    batch_op.add_column(sa.Column("google_sub", sa.String(length=191), nullable=True))
                else:
                    batch_op.add_column(
                        sa.Column(
                            "email_verified",
                            sa.Boolean(),
                            nullable=False,
                            server_default=sa.true(),
                        )
                    )
    google_sub_column = user_columns.get("google_sub")
    google_sub_length = getattr(google_sub_column["type"], "length", None) if google_sub_column else None
    if google_sub_length and google_sub_length > 191:
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "google_sub",
                existing_type=sa.String(length=google_sub_length),
                type_=sa.String(length=191),
                nullable=True,
            )

    user_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    if "uq_users_google_sub" not in user_indexes:
        op.create_index("uq_users_google_sub", "users", ["google_sub"], unique=True)

    if "email_verification_tokens" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )

    token_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("email_verification_tokens")
    }
    for index_name, column_name in (
        ("ix_email_verification_tokens_user_id", "user_id"),
        ("ix_email_verification_tokens_expires_at", "expires_at"),
    ):
        if index_name not in token_indexes:
            op.create_index(index_name, "email_verification_tokens", [column_name])


def downgrade() -> None:
    op.drop_index("ix_email_verification_tokens_expires_at", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_index("uq_users_google_sub", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("email_verified")
        batch_op.drop_column("google_sub")
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=False,
        )