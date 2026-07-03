"""Initial schema with all OECD tables

Revision ID: 001
Revises:
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(), nullable=False, server_default="oecd"),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("request_payload", JSONB, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ingestion_runs_source", "ingestion_runs", ["source"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"])

    op.create_table(
        "oecd_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ingestion_run_id", UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.id"), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("dataset_id", sa.String(), nullable=True),
        sa.Column("dataflow_id", sa.String(), nullable=True),
        sa.Column("structure_id", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("indicator_code", sa.String(), nullable=True),
        sa.Column("start_period", sa.String(), nullable=True),
        sa.Column("end_period", sa.String(), nullable=True),
        sa.Column("query_params", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oecd_requests_ingestion_run_id", "oecd_requests", ["ingestion_run_id"])
    op.create_index("ix_oecd_requests_endpoint", "oecd_requests", ["endpoint"])
    op.create_index("ix_oecd_requests_dataset_id", "oecd_requests", ["dataset_id"])
    op.create_index("ix_oecd_requests_dataflow_id", "oecd_requests", ["dataflow_id"])
    op.create_index("ix_oecd_requests_country", "oecd_requests", ["country"])
    op.create_index("ix_oecd_requests_indicator_code", "oecd_requests", ["indicator_code"])

    op.create_table(
        "raw_api_responses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("oecd_request_id", UUID(as_uuid=True), sa.ForeignKey("oecd_requests.id"), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("request_payload", JSONB, nullable=False),
        sa.Column("response_payload", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_raw_api_responses_oecd_request_id", "raw_api_responses", ["oecd_request_id"])
    op.create_index("ix_raw_api_responses_endpoint", "raw_api_responses", ["endpoint"])

    op.create_table(
        "oecd_dataflows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("oecd_request_id", UUID(as_uuid=True), sa.ForeignKey("oecd_requests.id"), nullable=False),
        sa.Column("agency_id", sa.String(), nullable=True),
        sa.Column("dataflow_id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oecd_dataflows_dataflow_id", "oecd_dataflows", ["dataflow_id"])
    op.create_index("ix_oecd_dataflows_agency_id", "oecd_dataflows", ["agency_id"])

    op.create_table(
        "oecd_datastructures",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("oecd_request_id", UUID(as_uuid=True), sa.ForeignKey("oecd_requests.id"), nullable=False),
        sa.Column("dataflow_id", sa.String(), nullable=True),
        sa.Column("structure_id", sa.String(), nullable=True),
        sa.Column("dimension_id", sa.String(), nullable=True),
        sa.Column("dimension_name", sa.Text(), nullable=True),
        sa.Column("dimension_position", sa.Integer(), nullable=True),
        sa.Column("code_id", sa.String(), nullable=True),
        sa.Column("code_name", sa.Text(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oecd_datastructures_dataflow_id", "oecd_datastructures", ["dataflow_id"])
    op.create_index("ix_oecd_datastructures_structure_id", "oecd_datastructures", ["structure_id"])
    op.create_index("ix_oecd_datastructures_dimension_id", "oecd_datastructures", ["dimension_id"])
    op.create_index("ix_oecd_datastructures_code_id", "oecd_datastructures", ["code_id"])

    op.create_table(
        "oecd_observations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("oecd_request_id", UUID(as_uuid=True), sa.ForeignKey("oecd_requests.id"), nullable=False),
        sa.Column("dataset_id", sa.String(), nullable=True),
        sa.Column("dataflow_id", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=False),
        sa.Column("indicator_code", sa.String(), nullable=False),
        sa.Column("indicator_name", sa.Text(), nullable=True),
        sa.Column("measure", sa.String(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("frequency", sa.String(), nullable=True),
        sa.Column("time_period", sa.String(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("normalized_value", sa.Numeric(), nullable=True),
        sa.Column("attributes", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oecd_observations_oecd_request_id", "oecd_observations", ["oecd_request_id"])
    op.create_index("ix_oecd_observations_dataset_id", "oecd_observations", ["dataset_id"])
    op.create_index("ix_oecd_observations_dataflow_id", "oecd_observations", ["dataflow_id"])
    op.create_index("ix_oecd_observations_country", "oecd_observations", ["country"])
    op.create_index("ix_oecd_observations_indicator_code", "oecd_observations", ["indicator_code"])
    op.create_index("ix_oecd_observations_time_period", "oecd_observations", ["time_period"])

    op.create_table(
        "oecd_indicators_catalog",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("indicator_code", sa.String(), nullable=False),
        sa.Column("indicator_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("expected_unit", sa.String(), nullable=True),
        sa.Column("marketmind_dimension", sa.String(), nullable=True),
        sa.Column("dataflow_id", sa.String(), nullable=True),
        sa.Column("dataset_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oecd_indicators_catalog_indicator_code", "oecd_indicators_catalog", ["indicator_code"])
    op.create_index("ix_oecd_indicators_catalog_category", "oecd_indicators_catalog", ["category"])
    op.create_index(
        "ix_oecd_indicators_catalog_marketmind_dimension", "oecd_indicators_catalog", ["marketmind_dimension"]
    )
    op.create_index("ix_oecd_indicators_catalog_is_active", "oecd_indicators_catalog", ["is_active"])


def downgrade() -> None:
    op.drop_table("oecd_indicators_catalog")
    op.drop_table("oecd_observations")
    op.drop_table("oecd_datastructures")
    op.drop_table("oecd_dataflows")
    op.drop_table("raw_api_responses")
    op.drop_table("oecd_requests")
    op.drop_table("ingestion_runs")
