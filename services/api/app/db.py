from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(value: str) -> str:
    try:
        url = make_url(value)
    except ArgumentError as exc:
        raise ValueError("Database URL is invalid.") from exc
    if url.get_backend_name() not in ("postgres", "postgresql"):
        return value
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername != "postgresql+psycopg":
        raise ValueError("PostgreSQL connections must use Psycopg 3")
    return url.render_as_string(hide_password=False)


database_url = normalize_database_url(settings.runtime_database_url)
is_sqlite = make_url(database_url).get_backend_name() == "sqlite"
engine_options: dict[str, object] = {
    "hide_parameters": True,
    "pool_pre_ping": True,
}
if is_sqlite:
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options["connect_args"] = {"prepare_threshold": None}
    engine_options.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
    )
engine = create_engine(database_url, **engine_options)
if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def sqlite_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
