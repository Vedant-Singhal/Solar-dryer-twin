from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DRYER_",
        extra="ignore",
        protected_namespaces=(),  # we use field names like model_path / model_version
    )

    env: str = "dev"
    model_path: Path = Path("models/surrogate-v1.joblib")
    model_version: str = "v1"

    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600
    cache_round_decimals: int = 2

    # Default to SQLite so the API runs out-of-the-box without Postgres.
    # docker-compose overrides this with the postgres URL for production-like dev.
    database_url: str = "sqlite:///./dryer.db"

    hf_min: float = 300.0
    hf_max: float = 800.0
    porosity_min: float = 0.5
    porosity_max: float = 0.9


settings = Settings()
