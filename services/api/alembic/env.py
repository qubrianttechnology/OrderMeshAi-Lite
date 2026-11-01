from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from alembic import context
from app import models  # noqa: F401
from app.config import settings
from app.db import Base, engine, normalize_database_url

configured_migration_url = settings.migration_database_url.get_secret_value().strip()
migration_url = normalize_database_url(settings.resolved_migration_database_url)
if configured_migration_url:
    migration_options = {"pool_pre_ping": True, "hide_parameters": True}
    if make_url(migration_url).get_backend_name() == "sqlite":
        migration_options["connect_args"] = {"check_same_thread": False}
    else:
        migration_options["connect_args"] = {"prepare_threshold": None}
    migration_engine = create_engine(migration_url, **migration_options)
else:
    migration_engine = engine

with migration_engine.connect() as connection:
    context.configure(
        connection=connection, target_metadata=Base.metadata, compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()

if migration_engine is not engine:
    migration_engine.dispose()
