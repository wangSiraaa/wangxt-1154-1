from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_host: str = "0.0.0.0"
    app_port: int = 18454
    api_port: int = 19454

    db_host: str = "localhost"
    db_port: int = 21454
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "waste_transfer"

    redis_host: str = "localhost"
    redis_port: int = 22454
    redis_db: int = 0

    weight_diff_threshold_pct: float = 5.0
    weight_diff_abs_threshold_kg: float = 200.0
    route_deviation_threshold_km: float = 2.0

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
