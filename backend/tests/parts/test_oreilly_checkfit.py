import json

import pytest

from gaswise.providers.parts.oreilly_checkfit import check_products


class Session:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def read(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.reply


@pytest.mark.asyncio
async def test_native_multicategory_exact_echo():
    session = Session(
        json.dumps(
            {
                "products": {
                    "DOR-090-164": {"fits": "COMPATIBLE"},
                    "KAN-HP7040": {"fits": "COMPATIBLE"},
                    "WIX-57060": {"fits": "INCOMPATIBLE"},
                    "OTHER-1": {"fits": "COMPATIBLE"},
                }
            }
        )
    )
    products = [
        {"lineCode": line, "itemNumber": item}
        for line, item in [("DOR", "090-164"), ("KAN", "HP7040"), ("WIX", "57060"), ("DOR", "missing")]
    ]
    result = await check_products(session, products, selected_vehicle_verified=True)
    assert [r["status"] for r in result] == ["matched", "matched", "incompatible", "unavailable"]
    assert session.calls[0][1]["json_body"] == [{"lineCodeItemNumber": p} for p in products]


@pytest.mark.asyncio
async def test_requires_verified_same_session_vehicle():
    session = Session("{}")
    with pytest.raises(ValueError, match="selected_vehicle_session_not_verified"):
        await check_products(session, [{"lineCode": "DOR", "itemNumber": "090-164"}])
    assert not session.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ["UNKNOWN", "UNIVERSAL", "NEW_FLAG", None])
async def test_uncertain_flags_never_become_fit_or_rejection(flag):
    session = Session(json.dumps({"products": {"DOR-1": {"fits": flag}}}))
    result = await check_products(
        session, [{"lineCode": "DOR", "itemNumber": "1"}], selected_vehicle_verified=True
    )
    assert result[0]["status"] in {"conditional", "unavailable"}
