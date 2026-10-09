from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PriceSourceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    url: HttpUrl
    token: SecretStr = SecretStr("")
    enabled: bool = True
    timeout_seconds: float = Field(default=15, ge=0.1, le=45)

    @model_validator(mode="after")
    def secure_endpoint(self):
        if self.url.scheme != "https":
            raise ValueError("Price source requires HTTPS")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GASWISE_", env_file=".env", extra="ignore")
    price_sources: list[PriceSourceSettings] = Field(default_factory=list, max_length=20)
    mode: Literal["demo", "google", "prices_only"] = "demo"
    google_api_key: SecretStr = SecretStr("")
    gasbuddy_web_enabled: bool = False
    gasbuddy_web_transport: Literal["http", "browser", "session_http"] = "http"
    gasbuddy_session_seconds: int = Field(default=600, ge=60, le=1800)
    gasbuddy_browser_channel: Literal["chrome", "chromium"] = "chrome"
    gasbuddy_browser_headless: bool = True
    gasbuddy_browser_timeout_seconds: int = Field(default=35, ge=5, le=45)
    gasbuddy_feed_url: HttpUrl | None = None
    gasbuddy_feed_token: SecretStr = SecretStr("")
    api_token: SecretStr = SecretStr("")
    cors_origins: list[str] = ["http://localhost:5173"]
    refresh_seconds: int = Field(default=300, ge=60, le=3600)
    max_concurrent_searches: int = Field(default=2, ge=1, le=20)

    @model_validator(mode="after")
    def live_credentials(self):
        if self.google_api_key.get_secret_value() and not self.api_token.get_secret_value():
            raise ValueError("Google prices require API_TOKEN")
        if self.mode == "prices_only" and not (
            self.gasbuddy_web_enabled or any(s.enabled for s in self.price_sources)
        ):
            raise ValueError("prices_only mode requires GasBuddy website source enabled")
        ids = [source.source_id for source in self.price_sources]
        if len(ids) != len(set(ids)) or set(ids) & {
            "gasbuddy",
            "gasbuddy_web",
            "google_places",
            "synthetic",
            "gasbuddy_demo",
        }:
            raise ValueError("Price source IDs must be unique and not reserved")
        if any(s.enabled for s in self.price_sources) and not self.api_token.get_secret_value():
            raise ValueError("Live price sources require API_TOKEN")
        if self.mode == "demo" and any(s.enabled for s in self.price_sources):
            raise ValueError("Live price sources cannot be mixed into demo mode")
        if self.mode == "google" and (
            not self.google_api_key.get_secret_value() or not self.api_token.get_secret_value()
        ):
            raise ValueError("Google mode requires GOOGLE_API_KEY and API_TOKEN")
        if (self.gasbuddy_web_enabled or self.gasbuddy_feed_url) and not self.api_token.get_secret_value():
            raise ValueError("Live GasBuddy sources require API_TOKEN")
        if self.gasbuddy_feed_url and (
            self.gasbuddy_feed_url.scheme != "https" or not self.gasbuddy_feed_token.get_secret_value()
        ):
            raise ValueError("GasBuddy feed requires HTTPS and feed token")
        return self
