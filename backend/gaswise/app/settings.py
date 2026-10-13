from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, field_validator, model_validator
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
    model_config = SettingsConfigDict(
        env_prefix="GASWISE_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )
    price_sources: list[PriceSourceSettings] = Field(default_factory=list, max_length=20)
    mode: Literal["demo", "google", "prices_only"] = "demo"
    google_routes_enabled: bool = False
    maps_web_routes_enabled: bool = False
    google_api_key: SecretStr = SecretStr("")
    maps_web_session_file: Path | None = None
    waze_enabled: bool = False
    waze_auto_login: bool = True
    waze_session_file: Path = Path.home() / ".config/gaswise/waze-http-session.json"
    waze_login_file: Path = Path.home() / ".config/gaswise/waze-http-login.bin"
    gasbuddy_web_enabled: bool = False
    # TOP TIER licensed-brand list: scheduled refresh, never per search; a bundled snapshot is the fallback.
    top_tier_refresh_enabled: bool = True
    top_tier_refresh_hours: int = Field(default=168, ge=24, le=2160)
    top_tier_cache_file: Path | None = Path.home() / ".cache/gaswise/top-tier-brands.json"
    gasbuddy_web_transport: Literal["http", "browser", "session_http"] = "http"
    gasbuddy_http_client: Literal["httpx", "curl", "curl_chrome"] = "httpx"
    gasbuddy_session_seconds: int = Field(default=600, ge=60, le=1800)
    # One fixed operator-owned US egress (GasBuddy serves US traffic only); never user supplied.
    gasbuddy_http_proxy: HttpUrl | None = None
    gasbuddy_browser_channel: Literal["chrome", "chromium"] = "chrome"
    gasbuddy_browser_headless: bool = True
    gasbuddy_browser_timeout_seconds: int = Field(default=35, ge=5, le=45)
    gasbuddy_feed_url: HttpUrl | None = None
    gasbuddy_feed_token: SecretStr = SecretStr("")
    api_token: SecretStr = SecretStr("")
    plate_lookup_enabled: bool = False
    plate_lookup_source: Literal["vehicle_databases", "autozone"] = "vehicle_databases"
    vehicle_databases_api_key: SecretStr = SecretStr("")
    parts_sources_enabled: bool = True
    parts_http_transport: Literal["curl", "httpx"] = "curl"
    vehicle_specifications_enabled: bool = True
    vehicle_specifications_transport: Literal["curl", "httpx"] = "curl"
    cors_origins: list[str] = ["http://localhost:5173"]
    refresh_seconds: int = Field(default=300, ge=60, le=3600)
    max_concurrent_searches: int = Field(default=2, ge=1, le=20)

    @field_validator("maps_web_session_file", "top_tier_cache_file", mode="before")
    @classmethod
    def empty_maps_session_is_anonymous(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def live_credentials(self):
        if self.plate_lookup_enabled and (
            not self.api_token.get_secret_value()
            or (
                self.plate_lookup_source == "vehicle_databases"
                and not self.vehicle_databases_api_key.get_secret_value()
            )
        ):
            raise ValueError("Plate lookup requires API_TOKEN and a key when using Vehicle Databases")
        if self.maps_web_routes_enabled and (self.mode == "demo" or not self.api_token.get_secret_value()):
            raise ValueError("Maps website routing requires live mode and API_TOKEN")
        if self.google_api_key.get_secret_value() and not self.api_token.get_secret_value():
            raise ValueError("Google prices require API_TOKEN")
        if self.maps_web_session_file and not self.api_token.get_secret_value():
            raise ValueError("Google Maps session source requires API_TOKEN")
        if self.mode == "prices_only" and not (
            self.gasbuddy_web_enabled
            or self.waze_enabled
            or self.maps_web_session_file
            or any(s.enabled for s in self.price_sources)
        ):
            raise ValueError("prices_only mode requires GasBuddy website source enabled")
        ids = [source.source_id for source in self.price_sources]
        if len(ids) != len(set(ids)) or set(ids) & {
            "gasbuddy",
            "gasbuddy_web",
            "google_places",
            "google_maps_web",
            "synthetic",
            "gasbuddy_demo",
            "waze",
        }:
            raise ValueError("Price source IDs must be unique and not reserved")
        if any(s.enabled for s in self.price_sources) and not self.api_token.get_secret_value():
            raise ValueError("Live price sources require API_TOKEN")
        if self.waze_enabled and not self.api_token.get_secret_value():
            raise ValueError("Live Waze source requires API_TOKEN")
        if self.waze_enabled and self.mode == "demo":
            raise ValueError("Live Waze source cannot be mixed into demo mode")
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
