from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    backend_cors_origins: str = "http://localhost:3000"
    minio_endpoint: str = "minio:9000"
    minio_bucket: str = "supplyflow"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin_secret"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
