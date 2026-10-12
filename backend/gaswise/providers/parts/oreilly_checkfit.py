"""Category-independent native checkfit protocol for an established vehicle session.

The caller must first verify the selected vehicle in the same retailer session.
This protocol does not bootstrap browser verification or infer fit from alternatives.
"""

import json
import re

ROOT = "https://www.oreillyauto.com"
FLAGS = {
    "COMPATIBLE": "matched",
    "INCOMPATIBLE": "incompatible",
    "UNIVERSAL": "conditional",
    "UNKNOWN": "conditional",
}


async def check_products(session, products, *, selected_vehicle_verified=False):
    if not selected_vehicle_verified:
        raise ValueError("selected_vehicle_session_not_verified")
    if not products or len(products) > 20:
        raise ValueError("checkfit_batch_must_contain_1_to_20_products")
    identities = []
    for product in products:
        line, item = product.get("lineCode"), product.get("itemNumber")
        if not isinstance(line, str) or not re.fullmatch(r"[A-Z0-9]{1,12}", line):
            raise ValueError("invalid_line_code")
        if not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9 ._-]{1,80}", item):
            raise ValueError("invalid_item_number")
        identities.append({"lineCode": line, "itemNumber": item})
    body = await session.read(
        ROOT + "/checkfit/products",
        json_body=[{"lineCodeItemNumber": identity} for identity in identities],
        headers={"Accept": "application/json"},
    )
    try:
        data = json.loads(body or "null")
    except (TypeError, ValueError):
        data = None
    returned = data.get("products") if isinstance(data, dict) else None
    results = []
    for identity in identities:
        key = identity["lineCode"] + "-" + identity["itemNumber"]
        value = returned.get(key) if isinstance(returned, dict) else None
        flag = value.get("fits") if isinstance(value, dict) else None
        results.append({**identity, "status": FLAGS.get(flag, "unavailable"), "native_flag": flag})
    return results
