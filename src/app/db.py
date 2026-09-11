from sqlalchemy import (
    Column,
    Integer,
    String,
    Table,
    MetaData,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
    create_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from flask import g

from app.config import get_settings

settings = get_settings()

# SQLAlchemy engine and metadata
# Flask/psycopg2 is synchronous: normalise any async driver in the URL back to
# its sync equivalent so the same DATABASE_URL keeps working after the migration.
db_url = settings.database_url
if db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
if db_url.startswith("sqlite+aiosqlite://"):
    db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)

# SQLite uses a pool class that does not accept size/overflow arguments.
_engine_kwargs = {"echo": False}
if not db_url.startswith("sqlite"):
    _engine_kwargs.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )

engine = create_engine(db_url, **_engine_kwargs)
metadata = MetaData()

# Users table for authentication
users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(50), unique=True, nullable=False, index=True),
    Column("email", String(100), unique=True, nullable=False, index=True),
    Column("hashed_password", String(255), nullable=False),
    Column("is_active", Boolean, default=True, nullable=False),
    Column("created_date", DateTime, default=func.now(), nullable=False),
)

# Notes table with proper constraints
notes = Table(
    "notes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("title", String(255), nullable=False),
    Column("description", String(1000), nullable=False),
    Column("completed", Boolean, default=False, nullable=False, index=True),
    Column("is_deleted", Boolean, default=False, nullable=False, index=True),
    Column("tags", JSON, default=[], nullable=False),
    Column("created_date", DateTime, default=func.now(), nullable=False, index=True),
    Column("owner_id", Integer, ForeignKey("users.id"), nullable=False),
)

# Session factory
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_db():
    """Return the request-scoped session, creating it on first use.

    Replaces the FastAPI ``Depends(get_db)`` generator: Flask stores the session
    on the application context (``g``) and tears it down in ``close_db``.
    """
    if "db" not in g:
        g.db = SessionLocal()
    return g.db


def close_db(exc=None):
    """Teardown hook registered with ``app.teardown_appcontext``."""
    session = g.pop("db", None)
    if session is not None:
        session.close()
