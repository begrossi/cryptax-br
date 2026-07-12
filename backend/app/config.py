from pydantic_settings import BaseSettings, SettingsConfigDict

# Shipped placeholder. Encrypting credentials under it is refused, because it is
# public knowledge — anyone with the repo could decrypt stored API keys.
DEFAULT_SECRET_KEY = "change-me-in-production-32-chars!!"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite+aiosqlite:///./cryptax.db"
    secret_key: str = DEFAULT_SECRET_KEY
    coingecko_api_key: str = ""
    etherscan_api_key: str = ""
    # Shared secret required on every API request (header X-API-Token).
    # Empty = auth disabled (local dev only — the backend is then fully open).
    api_token: str = ""
    debug: bool = False

    @property
    def secret_key_is_default(self) -> bool:
        return self.secret_key == DEFAULT_SECRET_KEY


settings = Settings()
