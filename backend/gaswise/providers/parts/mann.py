"""Live manufacturer application rows, including per-row restrictions (no vehicle table)."""

import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote

from gaswise.providers.parts.product import clean, compact


class MannRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.depth = 0
        self.params = []
        self.text = []
        self.notes = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            if not self.depth:
                self.params, self.text, self.notes = [], [], []
            self.depth += 1
        if self.depth:
            for key, value in attrs.items():
                if value and "vehicleName%3D" in value:
                    self.params.append(value)
                if value and key in {"title", "data-original-title", "data-tippy-content"}:
                    self.notes.append(clean(re.sub("<[^>]*>", " ", value)))

    def handle_data(self, data):
        if self.depth:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "tr" and self.depth:
            self.depth -= 1
            if not self.depth:
                for encoded in self.params:
                    row = {
                        k: v[0]
                        for k, v in parse_qs(unquote(encoded).lstrip("?"), keep_blank_values=True).items()
                    }
                    allowed = (
                        "vehicleMake",
                        "vehicleName",
                        "modelSeriesName",
                        "vehicleModel",
                        "engineCode",
                        "ccm",
                        "vehicleManufacturedFrom",
                        "vehicleManufacturedTo",
                        "serialNumberRange",
                    )
                    row = {k: row.get(k, "") for k in allowed}
                    row["notes"] = " | ".join(dict.fromkeys(self.notes))
                    row["description"] = clean(" ".join(self.text))
                    # Serial restrictions can be visible text instead of a tooltip attribute.
                    if re.search(
                        r"(?:housing|plastic stem|center tube|engine number|chassis|serial number)",
                        row["description"],
                        re.I,
                    ):
                        row["notes"] = row["notes"] or row["description"]
                    existing = next((r for r in self.rows if all(r[k] == row[k] for k in allowed)), None)
                    if existing is None:
                        self.rows.append(row)
                    elif row["notes"]:
                        existing["notes"] = " | ".join(
                            dict.fromkeys(filter(None, [existing["notes"], row["notes"]]))
                        )


def match_mann_rows(vehicle, rows):
    candidates = []
    for row in rows:
        make = re.sub(r"\s*\(USA\)\s*$", "", row["vehicleMake"], flags=re.I)
        names = {compact(v) for v in (vehicle.model, vehicle.trim) if v}
        name = compact(row["vehicleName"])
        if compact(make) != compact(vehicle.make) or name not in names:
            continue
        year = row["vehicleModel"] if re.fullmatch(r"\d{4}", row["vehicleModel"]) else None
        try:
            first, last = int(row["vehicleManufacturedFrom"][:4]), int(row["vehicleManufacturedTo"][:4])
            liters = float(row["ccm"]) / 1000
        except (ValueError, TypeError):
            continue
        if (
            vehicle.year is None
            or (year is not None and int(year) != vehicle.year)
            or not first <= vehicle.year <= last
        ):
            continue
        if vehicle.engine_liters is None or abs(float(vehicle.engine_liters) - liters) > 0.06:
            continue
        candidates.append(row)
    if not candidates:
        return (
            "no_match",
            [],
            [],
            ["No matching manufacturer application; absence is not an explicit rejection."],
        )
    notes = list(dict.fromkeys(v for r in candidates for v in [r["notes"], r["serialNumberRange"]] if v))
    if notes:
        return "conditional", candidates, notes, ["Manufacturer lists production or equipment restrictions."]
    # This matches the catalog's YMM/displacement record, not an exact factory build sheet.
    return "matched", candidates, [], ["Manufacturer year/make/model/displacement application found."]
