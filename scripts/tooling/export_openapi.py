"""Run from backend via uv so imports resolve from the installed package."""

import json
from pathlib import Path

from gaswise.main import create_app
from gaswise.app.settings import Settings

path = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"
settings = Settings(
    mode="demo", _env_file=None, waze_enabled=False, gasbuddy_web_enabled=False,
    google_api_key="", api_token="", price_sources=[], gasbuddy_feed_url=None,
    plate_lookup_enabled=False, vehicle_databases_api_key="",
)
path.write_text(json.dumps(create_app(settings).openapi(), indent=2) + "\n")
print(path)
