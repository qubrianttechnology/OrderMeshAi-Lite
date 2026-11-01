from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

_DISABLED_CONFIG_VALUES = {
    "",
    "disabled",
    "disable",
    "null",
    "none",
    "unset",
    "not-set",
    "local-demo",
    "local-demo-disabled",
    "demo-disabled",
    "placeholder",
    "example",
}


def has_real_config(value: str | None) -> bool:
    if value is None:
        return False
    cleaned = value.strip()
    if not cleaned:
        return False
    lowered = cleaned.casefold()
    if lowered in _DISABLED_CONFIG_VALUES:
        return False
    for marker in ("local-demo-", "demo-", "placeholder-"):
        if lowered.startswith(marker):
            return False
    return True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
        validate_default=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

    database_url: SecretStr | None = None
    migration_database_url: SecretStr = SecretStr("")
    database_target_id: str = ""
    migration_database_target_id: str = ""
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout: int = 30
    app_env: Literal["development", "production"] = "development"
    app_origin: str = "http://localhost:3000"
    allow_registration: bool = True
    session_hours: int = 12
    invoice_font_path: str = ""
    ai_provider: Literal["local", "openai"] = "local"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    image_extraction_enabled: bool = True
    openai_vision_model: str = ""
    voice_transcription_enabled: bool = True
    openai_transcription_model: str = "gpt-transcribe"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: SecretStr = SecretStr("")
    google_oauth_redirect_uri: str = ""
    whatsapp_verify_token: SecretStr = SecretStr("")
    meta_app_id: str = ""
    meta_embedded_signup_config_id: str = ""
    meta_connection_encryption_key: SecretStr = SecretStr("")
    whatsapp_public_callback_url: str = ""
    meta_app_secret: SecretStr = SecretStr("")
    whatsapp_access_token: SecretStr = SecretStr("")
    whatsapp_phone_number_id: str = ""
    whatsapp_graph_api_version: str = ""
    whatsapp_allowed_test_recipients: str = ""
    whatsapp_test_mode: bool = True
    payhere_merchant_id: str = ""
    payhere_merchant_secret: SecretStr = SecretStr("")
    payhere_app_id: str = ""
    payhere_app_secret: SecretStr = SecretStr("")
    payhere_sandbox: bool = True
    payhere_notify_url: str = ""

    @property
    def google_oauth_ready(self) -> bool:
        return has_real_config(self.google_oauth_client_id) and has_real_config(
            self.google_oauth_client_secret.get_secret_value()
        )

    @property
    def resolved_google_oauth_redirect_uri(self) -> str:
        configured = self.google_oauth_redirect_uri.strip()
        if configured:
            return configured
        return f"{self.app_origin.rstrip('/')}/api/auth/google/callback"

    @property
    def runtime_database_url(self) -> str:
        configured = (
            self.database_url.get_secret_value().strip() if self.database_url else ""
        )
        if has_real_config(configured):
            return configured
        if self.app_env == "development":
            return "sqlite:///./ordermesh.db"
        raise ValueError(
            "DATABASE_URL is required outside local development; configure a PostgreSQL URL."
        )

    @property
    def resolved_migration_database_url(self) -> str:
        configured = self.migration_database_url.get_secret_value().strip()
        if has_real_config(configured):
            return configured
        if self.app_env == "production":
            raise ValueError(
                "MIGRATION_DATABASE_URL is required for production migrations."
            )
        return self.runtime_database_url

    @model_validator(mode="after")
    def production_checks(self):
        if self.ai_provider == "openai" and (
            not has_real_config(self.openai_api_key.get_secret_value())
            or not self.openai_model.strip()
        ):
            raise ValueError(
                "OPENAI_API_KEY and OPENAI_MODEL are required when AI_PROVIDER=openai"
            )
        runtime_raw = (
            self.database_url.get_secret_value().strip() if self.database_url else ""
        )
        migration_raw = self.migration_database_url.get_secret_value().strip()
        runtime_raw = runtime_raw if has_real_config(runtime_raw) else ""
        migration_raw = migration_raw if has_real_config(migration_raw) else ""
        if self.app_env == "production" and not runtime_raw:
            raise ValueError(
                "DATABASE_URL must be explicitly configured for production."
            )
        if runtime_raw:
            runtime = self._database_url(runtime_raw, "DATABASE_URL")
        elif self.app_env == "development":
            runtime = self._database_url("sqlite:///./ordermesh.db", "DATABASE_URL")
        else:
            runtime = None
        migration = (
            self._database_url(migration_raw, "MIGRATION_DATABASE_URL")
            if migration_raw
            else None
        )
        if self.app_env == "production":
            if runtime is None or runtime.get_backend_name() != "postgresql":
                raise ValueError("Production requires PostgreSQL")
            if not self.app_origin.startswith("https://"):
                raise ValueError("Production requires HTTPS APP_ORIGIN")
            if runtime.query.get("sslmode") not in (
                "require",
                "verify-ca",
                "verify-full",
            ):
                raise ValueError("Production PostgreSQL requires TLS")
            if (
                migration
                and migration.get_backend_name() == "postgresql"
                and migration.query.get("sslmode")
                not in (
                    "require",
                    "verify-ca",
                    "verify-full",
                )
            ):
                raise ValueError("Production migration PostgreSQL requires TLS")
        if migration:
            if not runtime_raw:
                raise ValueError(
                    "DATABASE_URL must be configured alongside MIGRATION_DATABASE_URL."
                )
            self._validate_same_database(runtime, migration)
        if (
            self.db_pool_size < 1
            or self.db_max_overflow < 0
            or self.db_pool_timeout < 1
        ):
            raise ValueError("Database pool settings must be positive integers")
        return self

    @staticmethod
    def _database_url(value: str, setting_name: str):
        try:
            url = make_url(value)
        except ArgumentError as exc:
            raise ValueError(
                f"{setting_name} must be a valid SQLAlchemy database URL."
            ) from exc
        backend = url.get_backend_name()
        if backend not in ("sqlite", "postgresql"):
            raise ValueError(
                f"{setting_name} must use a supported SQLite or PostgreSQL URL."
            )
        if backend == "postgresql" and url.drivername not in (
            "postgres",
            "postgresql",
            "postgresql+psycopg",
        ):
            raise ValueError(
                f"{setting_name} must use the supported Psycopg 3 PostgreSQL driver."
            )
        if backend == "postgresql" and (not url.host or not url.database):
            raise ValueError(
                f"{setting_name} must include a PostgreSQL host and database name."
            )
        return url

    def _validate_same_database(self, runtime, migration):
        if runtime.get_backend_name() != migration.get_backend_name():
            raise ValueError(
                "DATABASE_URL and MIGRATION_DATABASE_URL must target the same database."
            )
        if runtime.database != migration.database:
            raise ValueError(
                "DATABASE_URL and MIGRATION_DATABASE_URL must target the same database."
            )
        runtime_target = self.database_target_id.strip()
        migration_target = self.migration_database_target_id.strip()
        if bool(runtime_target) != bool(migration_target) or (
            runtime_target and runtime_target != migration_target
        ):
            raise ValueError(
                "DATABASE_TARGET_ID and MIGRATION_DATABASE_TARGET_ID must identify the same target."
            )
        if runtime.get_backend_name() == "sqlite":
            if runtime.host != migration.host:
                raise ValueError(
                    "DATABASE_URL and MIGRATION_DATABASE_URL must target the same database."
                )
            return
        same_endpoint = runtime.host == migration.host and (runtime.port or 5432) == (
            migration.port or 5432
        )
        if not same_endpoint and not runtime_target:
            raise ValueError(
                "Different PostgreSQL endpoints require matching DATABASE_TARGET_ID and MIGRATION_DATABASE_TARGET_ID values."
            )


settings = Settings()
