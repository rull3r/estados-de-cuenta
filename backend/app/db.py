"""Conexión a SQLite y sesión de SQLAlchemy."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .models import Base

config.ensure_dirs()

engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
    pool_pre_ping=True,
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Agrega columnas nuevas a bases de datos creadas con versiones anteriores."""
    additions = (
        ("progress_stage", "ALTER TABLE statements ADD COLUMN progress_stage VARCHAR(60) DEFAULT 'en cola'"),
        ("progress_percent", "ALTER TABLE statements ADD COLUMN progress_percent INTEGER DEFAULT 0"),
        ("started_at", "ALTER TABLE statements ADD COLUMN started_at DATETIME"),
        ("finished_at", "ALTER TABLE statements ADD COLUMN finished_at DATETIME"),
    )
    with engine.begin() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(statements)")}
        for name, ddl in additions:
            if name not in columns:
                connection.exec_driver_sql(ddl)
        connection.exec_driver_sql(
            "UPDATE statements SET progress_percent = 100, progress_stage = 'listo' "
            "WHERE status != 'procesando' AND progress_percent = 0"
        )


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
