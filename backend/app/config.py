from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite+aiosqlite:///./cryptax.db"
    secret_key: str = "change-me-in-production-32-chars!!"
    coingecko_api_key: str = ""
    etherscan_api_key: str = ""
    debug: bool = False


settings = Settings()
