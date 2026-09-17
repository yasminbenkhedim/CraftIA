import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

logger = logging.getLogger("uvicorn")

Base = declarative_base()

def get_engine():
    db_url = settings.DATABASE_URL
    try:
        if db_url.startswith("sqlite"):
            engine = create_engine(db_url, connect_args={"check_same_thread": False})
        else:
            engine = create_engine(db_url, pool_pre_ping=True)
            # Test connection
            with engine.connect() as conn:
                pass
        return engine
    except Exception as e:
        logger.warning(f"Could not connect to primary DB ({db_url}): {e}. Falling back to SQLite.")
        sqlite_url = "sqlite:///./createflow.db"
        return create_engine(sqlite_url, connect_args={"check_same_thread": False})

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Import every model before create_all so its table is registered on Base.metadata.
    # A model only referenced from an endpoint module would otherwise be missing at boot
    # and fail with "no such table" on first use.
    from app.models import user, job, execution_log, brand_kit  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_additive_migrations()


def _apply_additive_migrations():
    """
    Adds columns that were introduced after a database was first created.

    Base.metadata.create_all() only creates missing TABLES -- it never alters an
    existing one, so a new model column would raise "no such column" against a
    database that predates it. Each step here is additive and idempotent, so it is
    safe to run on every boot.
    """
    from sqlalchemy import inspect, text
    from app.core.plans import DEFAULT_PLAN, monthly_credits

    # Read from the plan config rather than written as literals, so changing the free
    # allowance in one place does not leave a stale number baked into this DDL.
    _default_plan = DEFAULT_PLAN.value
    _default_allowance = monthly_credits(DEFAULT_PLAN)

    additive_columns = {
        # table: {column: DDL type}
        "jobs": {"video_options": "TEXT", "title": "VARCHAR(120)", "artifact_expired_at": "DATETIME"},
        # Credits. plan and the two counters carry SQL defaults so existing rows land on
        # the free plan with its allowance rather than NULL. credits_reset_at is left
        # NULL on purpose -- ALTER TABLE cannot compute "one month from now" per row, and
        # credits.ensure_period_current() reads NULL as "period lapsed", so the first
        # request from each pre-existing account stamps a real period on it.
        "users": {
            "plan": f"VARCHAR(32) DEFAULT '{_default_plan}'",
            "credits_remaining": f"INTEGER DEFAULT {_default_allowance}",
            "credits_total": f"INTEGER DEFAULT {_default_allowance}",
            "credits_reset_at": "DATETIME",
        },
    }

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
    except Exception as e:
        logger.warning(f"Schema inspection failed ({e}); skipping additive migrations.")
        return

    for table, columns in additive_columns.items():
        if table not in existing_tables:
            continue  # create_all() just built it with every column.
        try:
            present = {c["name"] for c in inspector.get_columns(table)}
        except Exception as e:
            logger.warning(f"Could not inspect '{table}' ({e}); skipping.")
            continue

        for column, ddl_type in columns.items():
            if column in present:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
                logger.info(f"Schema migration: added {table}.{column} ({ddl_type}).")
            except Exception as e:
                logger.warning(f"Could not add {table}.{column} ({e}).")
