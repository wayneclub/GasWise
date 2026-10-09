"""Run from backend via uv so imports resolve from the installed package."""

import json
from pathlib import Path

from gaswise.main import create_app
from gaswise.settings import Settings

path = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"
path.write_text(json.dumps(create_app(Settings(mode="demo")).openapi(), indent=2) + "\n")
print(path)
