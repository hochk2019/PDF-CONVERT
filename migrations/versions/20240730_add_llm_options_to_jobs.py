"""add llm options column to jobs

Revision ID: 5c9a1a8e5dbd
Revises: 
Create Date: 2024-07-30 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5c9a1a8e5dbd"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("llm_options", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "llm_options")
