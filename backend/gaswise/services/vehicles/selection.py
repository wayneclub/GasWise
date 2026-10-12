"""Catalog-grounded text selection. Ask only differences; never choose the first ambiguous match."""

import re
import unicodedata
from difflib import SequenceMatcher

from gaswise.contracts.vehicles import VehicleChoice, VehicleResolution
from gaswise.domain.ports import ProviderError

ALIASES = {
    "benz": "Mercedes-Benz",
    "mercedes": "Mercedes-Benz",
    "mb": "Mercedes-Benz",
    "mercedes benz": "Mercedes-Benz",
    "賓士": "Mercedes-Benz",
    "奔驰": "Mercedes-Benz",
    "宾士": "Mercedes-Benz",
    "vw": "Volkswagen",
    "chevy": "Chevrolet",
}
BODY_LABELS = {
    "coupe": "Coupe 雙門",
    "convertible": "Convertible 敞篷",
    "wagon": "Wagon 旅行車",
    "other": "其他／目錄未標示車身",
}


def compact(text):
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text).casefold())


def body(text):
    value = text.casefold()
    if "coupe" in value or "coupé" in value:
        return "coupe"
    if "convertible" in value or "cabriolet" in value:
        return "convertible"
    if "wagon" in value:
        return "wagon"
    return "other"


def question(year, make, models, field, prompt, choices):
    return VehicleResolution(
        status="needs_input",
        year=year,
        make=make,
        matched_models=models,
        answer_field=field,
        question=prompt,
        choices=[VehicleChoice(value=value, label=label) for value, label in choices],
    )


def make_matches(text, aliases, fuzzy=False):
    found = []
    if not fuzzy:
        for alias, make in sorted(aliases, key=lambda pair: len(pair[0]), reverse=True):
            parts = re.findall(r"[\w]+", alias)
            pattern = r"(?<!\w)" + r"[\s_-]*".join(re.escape(p) for p in parts) + r"(?!\w)"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                found.append((make, match.span(), 1.0))
        return found
    tokens = list(re.finditer(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", text))
    for start in range(len(tokens)):
        for end in range(start, min(start + 3, len(tokens))):
            span = tokens[start].start(), tokens[end].end()
            fragment = text[span[0] : span[1]]
            if any(c.isdigit() for c in fragment):
                continue
            normalized = compact(fragment)
            if len(normalized) < 4:
                continue
            for alias, make in aliases:
                if len(compact(alias)) < 4:
                    continue
                score = SequenceMatcher(None, normalized, compact(alias)).ratio()
                if score >= 0.82:
                    found.append((make, span, score))
    return sorted(found, key=lambda item: (item[2], item[1][1] - item[1][0]), reverse=True)


def model_core(name):
    return compact(
        re.sub(
            r"\b(?:coupe|coupé|convertible|cabriolet|station|wagon|4\s*matic)\b",
            "",
            name,
            flags=re.IGNORECASE,
        )
    )


class VehicleSelector:
    def __init__(self, catalog):
        self.catalog = catalog

    async def resolve(self, request):
        selection = request.model_copy(deep=True)
        result = await self._resolve(selection)
        result.selection = selection
        result.missing_fields = [key for key in ("year", "make", "model") if not getattr(selection, key)]
        return result

    async def _resolve(self, request):
        text = unicodedata.normalize("NFKC", request.text)
        years = re.findall(r"(?<!\d)(?:19[89]\d|20\d{2})(?!\d)", text)
        if request.year is None:
            if len(set(years)) != 1:
                return question(
                    None,
                    None,
                    [],
                    "year",
                    "你的車是哪一年的？",
                    [(year, year) for year in sorted(set(years))],
                )
            request.year = int(years[0])
            if request.year < 1984:
                request.year = None
                return question(None, None, [], "year", "目前車型目錄從 1984 年起，請確認年份。", [])
        year = request.year
        text = re.sub(r"(?<!\d)(?:19[89]\d|20\d{2})(?!\d)", "", text).strip()
        makes = await self.catalog.menu("make", year=year)
        aliases = [(item.text, item.value) for item in makes.items]
        available = {compact(item.value): item.value for item in makes.items}
        aliases.extend(
            (alias, available[compact(make)]) for alias, make in ALIASES.items() if compact(make) in available
        )
        found = make_matches(text, aliases)
        distinct = {item[0] for item in found}
        make = None
        if request.make:
            explicit = {canonical for alias, canonical in aliases if compact(alias) == compact(request.make)}
            if len(explicit) == 1:
                make = explicit.pop()
            else:
                found = make_matches(request.make, aliases, fuzzy=True)
                choices = list(dict.fromkeys(item[0] for item in found))[:5]
                request.make = None
                return question(
                    year,
                    None,
                    [],
                    "make",
                    "請確認車廠。",
                    [(value, value) for value in choices] or [(i.value, i.text) for i in makes.items[:50]],
                )
        elif len(distinct) == 1:
            make = found[0][0]
        else:
            fuzzy = make_matches(text, aliases, fuzzy=True) if not distinct else []
            choices = sorted(distinct) if distinct else list(dict.fromkeys(item[0] for item in fuzzy))[:5]
            return question(
                year,
                None,
                [],
                "make",
                "你的車是哪個車廠／品牌？",
                [(value, value) for value in choices] or [(i.value, i.text) for i in makes.items[:50]],
            )
        request.make = make
        spans = [item[1] for item in found if item[0] == make]
        fuzzy = [item for item in make_matches(text, aliases, fuzzy=True) if item[0] == make]
        if spans:
            exact = max(spans, key=lambda s: s[1] - s[0])
            # Expand a misspelled prefix (mercedez benz), never consume the E in E 400.
            spans.extend(item[1] for item in fuzzy if item[1][1] == exact[1] and item[1][0] < exact[0])
            span = max(spans, key=lambda s: s[1] - s[0])
        else:
            span = fuzzy[0][1] if fuzzy else None
        remainder = text[: span[0]] + text[span[1] :] if span else text
        if request.model:
            remainder = unicodedata.normalize("NFKC", request.model)
        selected_body = request.body_style
        if selected_body is None and body(remainder) != "other":
            selected_body = body(remainder)
        drive = request.drivetrain
        has_4matic = bool(re.search(r"\b4\s*matic\b", remainder, re.IGNORECASE))
        has_standard = bool(re.search(r"\b(?:standard|rwd)\b|標準|後驅", remainder, re.IGNORECASE))
        if has_4matic and has_standard and drive is None:
            return question(
                year,
                make,
                [],
                "drivetrain",
                "請確認標準版或 4MATIC。",
                [("standard", "標準版（非 4MATIC）"), ("4matic", "4MATIC")],
            )
        if drive is None:
            drive = "4matic" if has_4matic else "standard" if has_standard else None
        base = compact(
            re.sub(
                r"\b(?:coupe|coupé|convertible|cabriolet|station|wagon|4\s*matic|standard|rwd)\b"
                r"|標準|後驅",
                "",
                remainder,
                flags=re.IGNORECASE,
            )
        )
        menu = await self.catalog.menu("model", year=year, make=make)
        if not base:
            return question(
                year, make, [], "model", "你的車是哪個型號？", [(i.value, i.text) for i in menu.items[:50]]
            )
        request.model = base
        request.body_style = selected_body
        request.drivetrain = drive
        matches = []
        for item in menu.items:
            name = compact(item.value)
            model_base = model_core(item.value)
            if not model_base.startswith(base) or (
                len(model_base) > len(base) and model_base[len(base)].isdigit()
            ):
                continue
            if selected_body is not None and body(item.value) != selected_body:
                continue
            if drive is not None and ("4matic" in name) != (drive == "4matic"):
                continue
            matches.append(item.value)
        if request.catalog_model is not None:
            matches = [name for name in matches if name == request.catalog_model]
        if not matches:
            suggestions = []
            for item in menu.items:
                core = model_core(item.value)
                if selected_body is not None and body(item.value) != selected_body:
                    continue
                if drive is not None and ("4matic" in compact(item.value)) != (drive == "4matic"):
                    continue
                if len(base) >= 2 and core.startswith(base):
                    suggestions.append((1.0, item.value))
                    continue
                # Preserve numeric model identities: E499 must not silently become E400.
                if re.findall(r"\d+", base) != re.findall(r"\d+", core):
                    continue
                score = SequenceMatcher(None, base, core).ratio()
                if score >= 0.78:
                    suggestions.append((score, item.value))
            if suggestions and request.catalog_model is None:
                values = [name for score, name in sorted(suggestions, reverse=True)[:10]]
                return question(
                    year, make, values, "model", "你是指以下哪個型號？", [(name, name) for name in values]
                )
            return VehicleResolution(
                status="no_match",
                year=year,
                make=make,
                answer_field="model",
                question="找不到這個型號，請確認或重新輸入。",
            )
        bodies = sorted({body(name) for name in matches})
        if len(bodies) > 1:
            return question(
                year,
                make,
                matches,
                "body_style",
                "你的車身是哪一種？",
                [(value, BODY_LABELS[value]) for value in bodies],
            )
        drives = {"4matic" in compact(name) for name in matches}
        if make == "Mercedes-Benz" and len(drives) > 1:
            return question(
                year,
                make,
                matches,
                "drivetrain",
                "是標準版還是 4MATIC 四輪驅動？",
                [("standard", "標準版（非 4MATIC）"), ("4matic", "4MATIC")],
            )
        core = compact(
            re.sub(
                r"\b(?:coupe|coupé|convertible|cabriolet|station|wagon|4\s*matic)\b",
                "",
                matches[0],
                flags=re.IGNORECASE,
            )
        )
        if len(matches) > 1 or (core != base and request.catalog_model is None):
            return question(
                year, make, matches, "catalog_model", "請確認確切車型。", [(name, name) for name in matches]
            )
        options = await self.catalog.menu("options", year=year, make=make, model=matches[0])
        choices = options.items
        if request.option_vehicle_id is not None:
            choices = [item for item in choices if item.value == str(request.option_vehicle_id)]
        if len(choices) > 1:
            return question(
                year,
                make,
                matches,
                "option_vehicle_id",
                "請確認引擎與變速箱配置。",
                [(item.value, item.text) for item in choices],
            )
        if not choices:
            return VehicleResolution(
                status="no_match", year=year, make=make, question="選擇的配置不屬於這個車型，請確認。"
            )
        try:
            vehicle_id = int(choices[0].value)
            if vehicle_id <= 0 or vehicle_id > 1000000:
                raise ValueError("invalid_vehicle_id")
        except ValueError:
            raise ProviderError("vehicle_catalog_invalid_option") from None
        vehicle = await self.catalog.vehicle(vehicle_id)
        if vehicle.year != year or vehicle.make != make or vehicle.model != matches[0]:
            raise ProviderError("vehicle_catalog_selection_mismatch")
        return VehicleResolution(
            status="resolved",
            year=year,
            make=make,
            matched_models=matches,
            vehicle=vehicle,
            fuel_recommendation=vehicle.fuel_recommendation,
        )
