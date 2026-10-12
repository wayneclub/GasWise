from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.common import Point
from gaswise.contracts.search import Search
from gaswise.contracts.smart import SmartSearch
from gaswise.contracts.vehicles import VehicleResolveRequest
from gaswise.main import create_app
from gaswise.providers.vehicles.catalog import VehicleProvider
from gaswise.services.pricing.search import SearchService
from gaswise.services.pricing.smart import SmartService
from gaswise.services.vehicles.selection import VehicleSelector
from tests.support.service import FixtureProvider
from tests.support.vehicles import RECORD

MODELS = [
    "E400 4matic",
    "E400 4matic (station wagon)",
    "E400 4matic Convertible",
    "E400 4matic Coupe",
    "E400 Convertible",
    "E400 Coupe",
    "E4000 Coupe",
]
IDS = {name: str(index + 100) for index, name in enumerate(MODELS)}


def handler(request):
    path = request.url.path
    if path.endswith("/menu/make"):
        rows = [{"text": "Mercedes-Benz", "value": "Mercedes-Benz"}, {"text": "Honda", "value": "Honda"}]
    elif path.endswith("/menu/model"):
        rows = [{"text": name, "value": name} for name in MODELS]
    elif path.endswith("/menu/options"):
        rows = [{"text": "Auto 9-spd, 6 cyl, 3.0 L, Turbo", "value": IDS[request.url.params["model"]]}]
    else:
        name = next(name for name, id in IDS.items() if id == path.rsplit("/", 1)[1])
        return httpx.Response(
            200,
            json={
                **RECORD,
                "id": IDS[name],
                "year": "2018",
                "make": "Mercedes-Benz",
                "model": name,
                "comb08": "22",
            },
        )
    return httpx.Response(200, json={"menuItem": rows})


async def test_benz_e400_asks_body_then_drive_then_resolves():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        selector = VehicleSelector(VehicleProvider(client))
        first = await selector.resolve(VehicleResolveRequest(text="2018 benz e400"))
        assert first.status == "needs_input"
        assert first.answer_field == "body_style"
        assert "E4000 Coupe" not in first.matched_models
        second = await selector.resolve(VehicleResolveRequest(text="2018 benz e400", body_style="coupe"))
        assert second.answer_field == "drivetrain"
        assert {choice.value for choice in second.choices} == {"standard", "4matic"}
        final = await selector.resolve(
            VehicleResolveRequest(text="2018 benz e400", body_style="coupe", drivetrain="4matic")
        )
        assert final.status == "resolved"
        assert final.vehicle.model == "E400 4matic Coupe"
        assert final.vehicle.combined_mpg == Decimal(22)
        assert final.fuel_recommendation.fuel_type == "premium"
        assert final.fuel_recommendation.octane_aki is None
        assert final.fuel_recommendation.manufacturer_requirement_verified is False


@pytest.mark.parametrize(
    "text",
    [
        "2018 benz e400 coupe 4MATIC",
        "2018 Mercedes-Benz E 400 4matic Coupe",
        "2018 mercedes benz E400 Coupe 4 matic",
    ],
)
async def test_complete_input_skips_questions(text):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(VehicleResolveRequest(text=text))
    assert result.status == "resolved"
    assert result.vehicle.model == "E400 4matic Coupe"


async def test_standard_input_does_not_select_4matic():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(
            VehicleResolveRequest(text="2018 benz e400 coupe standard")
        )
    assert result.vehicle.model == "E400 Coupe"


@pytest.mark.parametrize(
    "text,field",
    [
        ("benz e400", "year"),
        ("2018 e400", "make"),
        ("2018 benz", "model"),
        ("2018 benz e400 standard 4matic", "drivetrain"),
    ],
)
async def test_missing_or_conflicting_input_requires_answer(text, field):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(VehicleResolveRequest(text=text))
    assert result.status == "needs_input"
    assert result.answer_field == field
    assert result.vehicle is None


async def test_invalid_choice_cannot_select_different_vehicle():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(
            VehicleResolveRequest(
                text="2018 benz e400 coupe",
                drivetrain="standard",
                option_vehicle_id=999,
            )
        )
    assert result.status == "no_match"
    assert result.vehicle is None


async def test_unknown_model_not_guessed():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(
            VehicleResolveRequest(text="2018 benz e499")
        )
    assert result.status == "no_match"


async def test_multiple_engine_options_are_not_silently_selected():
    def several(request):
        if request.url.path.endswith("/menu/options"):
            return httpx.Response(
                200,
                json={
                    "menuItem": [
                        {"text": "Automatic", "value": "105"},
                        {"text": "Manual", "value": "999"},
                    ]
                },
            )
        return handler(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(several)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(
            VehicleResolveRequest(text="2018 benz e400 coupe standard")
        )
    assert result.status == "needs_input"
    assert result.answer_field == "option_vehicle_id"
    assert result.vehicle is None


async def test_partial_model_needs_confirmation_even_when_unique():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(
            VehicleResolveRequest(text="2018 benz e4 coupe standard")
        )
    assert result.status != "resolved"


async def test_auto_fuel_reaches_price_query_and_snapshot():
    class CaptureProvider(FixtureProvider):
        async def stations(self, query):
            assert query.fuel_type == "regular"
            return []

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={**RECORD, "fuelType1": "Regular Gasoline"})
        )
    ) as client:
        catalog = VehicleProvider(client)
        result = await SearchService(CaptureProvider(), "demo", vehicles=catalog).search(
            Search(origin=Point(lat=34, lng=-118), vehicle_id=123)
        )
        assert result.vehicle.fuel_recommendation.fuel_type == "regular"
        smart = SmartService(b"test", "demo", demo=CaptureProvider(), vehicles=catalog)
        snapshot = await smart.search(SmartSearch(origin=Point(lat=34, lng=-118), vehicle_id=123))
        assert snapshot.snapshot.query.fuel_type == "regular"
        assert snapshot.snapshot.vehicle.fuel_recommendation.fuel_type == "regular"


def test_resolver_http_endpoint():
    with TestClient(
        create_app(
            Settings(),
            FixtureProvider(),
            vehicle_provider=VehicleProvider(httpx.AsyncClient(transport=httpx.MockTransport(handler))),
        )
    ) as client:
        result = client.post("/v1/vehicles/resolve", json={"text": "2018 benz e400 coupe 4matic"})
        assert result.status_code == 200
        assert result.json()["status"] == "resolved"
        assert result.json()["fuel_recommendation"]["fuel_type"] == "premium"


@pytest.mark.parametrize(
    "text",
    [
        "2018 mercedes benz e400",
        "２０１８　Ｍｅｒｃｅｄｅｓ　Ｂｅｎｚ　Ｅ４００",
        "2018 mercedes   benz e 400",
        "2018 Mercedes_Benz E400",
    ],
)
async def test_spacing_punctuation_width_and_aliases(text):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(VehicleResolveRequest(text=text))
    assert result.answer_field == "body_style"
    assert result.make == "Mercedes-Benz"
    assert result.selection.model == "e400"


async def test_empty_query_progressively_collects_year_make_model_and_configuration():
    calls = []

    def counted(request):
        calls.append(request)
        return handler(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(counted)) as client:
        selector = VehicleSelector(VehicleProvider(client))
        first = await selector.resolve(VehicleResolveRequest())
        assert first.answer_field == "year"
        assert first.missing_fields == ["year", "make", "model"]
        assert not calls
        second = await selector.resolve(first.selection.model_copy(update={"year": 2018}))
        assert second.answer_field == "make"
        assert second.missing_fields == ["make", "model"]
        third = await selector.resolve(second.selection.model_copy(update={"make": "benz"}))
        assert third.answer_field == "model"
        assert third.missing_fields == ["model"]
        fourth = await selector.resolve(third.selection.model_copy(update={"model": "E400 Coupe"}))
        assert fourth.answer_field == "drivetrain"
        assert fourth.missing_fields == []
        final = await selector.resolve(fourth.selection.model_copy(update={"drivetrain": "4matic"}))
        assert final.status == "resolved"
        assert final.vehicle.model == "E400 4matic Coupe"


async def test_missing_year_preserves_original_text_after_answer():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        selector = VehicleSelector(VehicleProvider(client))
        first = await selector.resolve(VehicleResolveRequest(text="benz e400 coupe standard"))
        final = await selector.resolve(first.selection.model_copy(update={"year": 2018}))
    assert final.status == "resolved"
    assert final.vehicle.model == "E400 Coupe"


async def test_typo_make_suggests_and_requires_confirmation():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        selector = VehicleSelector(VehicleProvider(client))
        first = await selector.resolve(VehicleResolveRequest(text="2018 mercedez e400 coupe standard"))
        assert first.answer_field == "make"
        assert "Mercedes-Benz" in [item.value for item in first.choices]
        assert first.vehicle is None
        final = await selector.resolve(first.selection.model_copy(update={"make": "Mercedes-Benz"}))
    assert final.status == "resolved"


async def test_model_typo_suggests_and_requires_confirmation():
    def honda(request):
        if request.url.path.endswith("/menu/model"):
            return httpx.Response(200, json={"menuItem": [{"text": "Accord", "value": "Accord"}]})
        return handler(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(honda)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(
            VehicleResolveRequest(text="2018 Honda acocrd")
        )
    assert result.answer_field == "model"
    assert result.choices[0].value == "Accord"
    assert result.vehicle is None


async def test_conflicting_drive_can_be_answered_without_retyping():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        selector = VehicleSelector(VehicleProvider(client))
        first = await selector.resolve(VehicleResolveRequest(text="2018 benz e400 coupe standard 4matic"))
        final = await selector.resolve(first.selection.model_copy(update={"drivetrain": "standard"}))
    assert final.status == "resolved"
    assert final.vehicle.model == "E400 Coupe"


async def test_conflicting_years_can_be_answered_with_year_field():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        selector = VehicleSelector(VehicleProvider(client))
        first = await selector.resolve(VehicleResolveRequest(text="2017 2018 benz e400 coupe standard"))
        assert first.answer_field == "year"
        assert {choice.value for choice in first.choices} == {"2017", "2018"}
        final = await selector.resolve(first.selection.model_copy(update={"year": 2018}))
    assert final.status == "resolved"
    assert final.vehicle.year == 2018


async def test_misspelled_full_make_prefix_does_not_pollute_model():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await VehicleSelector(VehicleProvider(client)).resolve(
            VehicleResolveRequest(text="2018 mercedez benz e 400 coupe standard")
        )
    assert result.status == "resolved"


def test_http_empty_request_starts_questions_instead_of_validation_error():
    with TestClient(
        create_app(
            Settings(),
            FixtureProvider(),
            vehicle_provider=VehicleProvider(httpx.AsyncClient(transport=httpx.MockTransport(handler))),
        )
    ) as client:
        result = client.post("/v1/vehicles/resolve", json={})
    assert result.status_code == 200
    assert result.json()["answer_field"] == "year"
    assert result.json()["selection"]["text"] == ""
