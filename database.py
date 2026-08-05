import logging
import os
import time

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./database/case_builder.db",
)

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    } if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
    future=True,
    echo=False,
)

logger = logging.getLogger(__name__)

# Shared by every Gunicorn worker. PostgreSQL holds this transaction-level lock
# while SQLAlchemy checks/creates the schema, preventing concurrent CREATE TABLE
# and CREATE SEQUENCE statements during application startup.
SCHEMA_INIT_LOCK_ID = 1_866_273_148

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def initialize_database(
    *,
    db_engine=engine,
    max_attempts: int | None = None,
    initial_delay_seconds: float | None = None,
) -> None:
    """Create missing tables once, retrying temporary database outages."""
    attempts = max_attempts or int(
        os.getenv("DATABASE_INIT_MAX_ATTEMPTS", "5")
    )
    initial_delay = initial_delay_seconds or float(
        os.getenv("DATABASE_INIT_RETRY_DELAY_SECONDS", "1")
    )

    if attempts < 1:
        raise ValueError("DATABASE_INIT_MAX_ATTEMPTS must be at least 1.")
    if initial_delay <= 0:
        raise ValueError(
            "DATABASE_INIT_RETRY_DELAY_SECONDS must be greater than 0."
        )

    for attempt in range(1, attempts + 1):
        try:
            with db_engine.begin() as connection:
                if db_engine.dialect.name == "postgresql":
                    connection.execute(
                        text("SELECT pg_advisory_xact_lock(:lock_id)"),
                        {"lock_id": SCHEMA_INIT_LOCK_ID},
                    )

                Base.metadata.create_all(bind=connection)

            logger.info("Database schema is ready.")
            return
        except OperationalError:
            if attempt == attempts:
                logger.exception(
                    "Database was unavailable after %s attempts.",
                    attempts,
                )
                raise

            delay = min(initial_delay * (2 ** (attempt - 1)), 30.0)
            logger.warning(
                "Database is unavailable (attempt %s/%s); retrying in %.1f seconds.",
                attempt,
                attempts,
                delay,
            )
            time.sleep(delay)


def is_database_ready(*, db_engine=engine) -> bool:
    """Return whether the application can execute a trivial database query."""
    try:
        with db_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def get_db():
    db: Session = SessionLocal()

    try:
        yield db
    finally:
        db.close()
