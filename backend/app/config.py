from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_KEY = "change_me_in_production_min_32_chars"


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    backend_cors_origins: str = "http://localhost:3000"
    minio_endpoint: str = "minio:9000"
    minio_bucket: str = "supplyflow"
    minio_root_user: str
    minio_root_password: str
    debug: bool = False
    whatsapp_group_jid: str = ""          # пусто = не настроено
    whatsapp_curator_phone: str = ""

    model_config = SettingsConfigDict(env_file=".env")

    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        if not self.debug:
            if self.secret_key == _PLACEHOLDER_KEY or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters and not the default placeholder"
                )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",")]


settings = Settings()
