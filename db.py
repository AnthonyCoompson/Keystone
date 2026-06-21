"""
Keystone — Persistence Layer
© 2026 Anthony Coompson. All rights reserved.

Replaces localStorage as the source of truth for projects, components, audit
log entries, score history, and document-analysis history. Backed by Postgres
on Render in production (DATABASE_URL env var) and falling back to a local
SQLite file when DATABASE_URL is not set, so the app keeps working in local
development without provisioning a database.

Design notes:
- Tables mirror the existing localStorage record shapes field-for-field, so
  the frontend's sync layer can serialize/deserialize without reshaping data.
- A "device_id" column scopes data per browser/device by default. When a
  user explicitly shares a project (future feature), rows can be re-scoped
  to a shared workspace_id instead. For now device_id is the only scope,
  which mirrors today's "one browser, one set of projects" behaviour while
  adding real durability and cross-device portability via the sync token.
- All writes are idempotent upserts keyed by primary id, so repeated/retried
  syncs from a flaky connection never duplicate data.
"""

import os
import logging
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, Column, String, Integer, Text, DateTime, ForeignKey, JSON, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import OperationalError

logger = logging.getLogger("keystone.db")

# ── Engine setup ────────────────────────────────────────────────────────────
# Render's managed Postgres add-on injects DATABASE_URL as postgres://, but
# SQLAlchemy 2.x requires the postgresql:// scheme — normalise it here.
_raw_url = os.environ.get("DATABASE_URL", "").strip()
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)

DATABASE_URL = _raw_url or "sqlite:///./keystone_local.db"
IS_SQLITE = DATABASE_URL.startswith("sqlite")

_engine_kwargs = {"pool_pre_ping": True}
if IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def now_utc():
    return datetime.now(timezone.utc)


# ── Models ──────────────────────────────────────────────────────────────────
# JSON column type: Postgres gets native JSONB-compatible JSON; SQLite gets
# SQLAlchemy's JSON which serializes to TEXT transparently. Same Python API.

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)             # client-generated id (generateId())
    device_id = Column(String, index=True, nullable=False)
    name = Column(Text, nullable=False, default="")
    department = Column(Text, nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    mandate = Column(Text, nullable=False, default="")
    created_at = Column(Text, nullable=True)           # ISO string, preserved verbatim from client
    timeline = Column(JSON, nullable=True)              # saved Gantt timeline blob, or null
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class Component(Base):
    __tablename__ = "components"

    id = Column(String, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    type = Column(Text, nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    target_benchmark = Column(Text, nullable=False, default="")
    verification_source = Column(Text, nullable=False, default="")
    timeframe = Column(Text, nullable=True)             # only meaningful for Outcomes
    # Explicit relationship links — JSON list of component ids, or null if
    # the user has never touched the link picker for this component.
    linked_input_ids = Column(JSON, nullable=True)
    linked_output_ids = Column(JSON, nullable=True)
    linked_outcome_ids = Column(JSON, nullable=True)
    # Completeness rubric extra fields — baseline (Outcomes), responsible
    # party (Outputs). Nullable since most components won't set them.
    baseline = Column(Text, nullable=True)
    responsible_party = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id = Column(String, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    risk_level = Column(Text, nullable=False, default="")
    error_type = Column(Text, nullable=False, default="")
    message = Column(Text, nullable=False, default="")
    component_id = Column(String, nullable=True)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class ScoreHistoryEntry(Base):
    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, index=True, nullable=False)
    project_id = Column(String, index=True, nullable=False)
    score = Column(Integer, nullable=False)
    ts = Column(String, nullable=False)                 # client epoch-ms, kept as string for exactness


class DocAnalysisHistoryEntry(Base):
    __tablename__ = "doc_analysis_history"

    id = Column(String, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    file_name = Column(Text, nullable=False, default="")
    mandate = Column(Text, nullable=False, default="")
    timestamp = Column(String, nullable=False)           # client epoch-ms
    components = Column(JSON, nullable=False, default=list)


class ProjectVersion(Base):
    __tablename__ = "project_versions"

    id = Column(String, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    project_id = Column(String, index=True, nullable=False)
    label = Column(Text, nullable=False, default="")
    timestamp = Column(String, nullable=False)            # client epoch-ms
    mandate = Column(Text, nullable=False, default="")
    score = Column(Integer, nullable=False, default=0)
    components = Column(JSON, nullable=False, default=list)  # full snapshot
    findings = Column(JSON, nullable=False, default=list)    # audit findings at save time


class RuleSettings(Base):
    """Per-project overrides for the editable audit rules (completeness
    rubric, timeframe coherence). One row per project; absent row means the
    project uses DEFAULT_RULE_SETTINGS client-side."""
    __tablename__ = "rule_settings"

    project_id = Column(String, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    completeness = Column(JSON, nullable=False, default=dict)
    timeframe_coherence = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    try:
        Base.metadata.create_all(engine)
        logger.info(f"✓ Database ready ({'SQLite (local)' if IS_SQLITE else 'Postgres'}).")
    except OperationalError as exc:
        logger.error(f"Database connection failed: {exc}")
        raise


def get_session() -> Session:
    return SessionLocal()


# ── Upsert helpers ──────────────────────────────────────────────────────────
# Used by the sync endpoints. Postgres gets a real ON CONFLICT upsert;
# SQLite (local dev only) falls back to a manual merge, since SQLAlchemy's
# generic insert() doesn't support ON CONFLICT uniformly across dialects.

def _pk_column_name(model) -> str:
    """Return the name of the model's single primary-key column."""
    pk_cols = list(model.__table__.primary_key.columns)
    return pk_cols[0].name if pk_cols else "id"


def _upsert_postgres(session: Session, model, rows: list[dict]):
    if not rows:
        return
    table = model.__table__
    pk = _pk_column_name(model)
    stmt = pg_insert(table).values(rows)
    update_cols = {c.name: stmt.excluded[c.name] for c in table.columns if c.name != pk}
    stmt = stmt.on_conflict_do_update(index_elements=[pk], set_=update_cols)
    session.execute(stmt)


def _upsert_sqlite(session: Session, model, rows: list[dict]):
    pk = _pk_column_name(model)
    for row in rows:
        existing = session.get(model, row[pk])
        if existing:
            for k, v in row.items():
                setattr(existing, k, v)
        else:
            session.add(model(**row))


def upsert_rows(session: Session, model, rows: list[dict]):
    if IS_SQLITE:
        _upsert_sqlite(session, model, rows)
    else:
        _upsert_postgres(session, model, rows)
