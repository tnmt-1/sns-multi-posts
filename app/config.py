from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    secret_key: str = Field(default="dev_secret_key_change_me", alias="SECRET_KEY")
    debug: bool = Field(default=False, alias="DEBUG")

    # Twitter API
    twitter_client_id: str | None = Field(default=None, alias="TWITTER_CLIENT_ID")
    twitter_client_secret: str | None = Field(default=None, alias="TWITTER_CLIENT_SECRET")

    # Deployment
    vercel: bool = Field(default=False, alias="VERCEL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
