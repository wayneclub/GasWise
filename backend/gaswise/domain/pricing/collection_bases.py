"""Curated public SoCal sampling bases with official population/coordinate provenance."""

import json
from importlib.resources import files

BASE_CATALOG = json.loads(files(__package__).joinpath("socal_bases.json").read_text())
BASES = {base["id"]: (base["lat"], base["lng"]) for base in BASE_CATALOG["bases"]}
