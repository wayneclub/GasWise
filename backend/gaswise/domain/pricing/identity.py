"""Conservative crosswalks within one search inventory; never match by brand alone."""

import re

from gaswise.domain.pricing.comparison import distance_meters

STATE_CODES = dict(zip(
    "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|District of Columbia|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming".lower().split("|"),
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(),
    strict=True,
))
STATE_SUFFIX = re.compile(r"\b(" + "|".join(STATE_CODES) + r")\s+(\d{5}(?:-\d{4})?)\b", re.IGNORECASE)


def normalized_address(address):
    # Normalize the explicit state immediately before ZIP, not city/street names.
    return STATE_SUFFIX.sub(lambda m: STATE_CODES[m[1].lower()] + " " + m[2], address or "")


def address_key(address):
    # ZIP+4 identifies delivery detail; both sources must still agree on ZIP5.
    address = re.sub(r"\b(\d{5})-\d{4}\b", r"\1", normalized_address(address))
    return re.sub(r"[^a-z0-9]", "", address.lower())


def inventory_match(inventory, address, location=None):
    # Require a full US street/city/state/ZIP address, not a shared display name.
    address = normalized_address(address)
    if not address or not re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", address):
        return None
    matches = [row for row in inventory if address_key(row.address) == address_key(address)]
    if len(matches) != 1:
        return None
    row = matches[0]
    if location is not None and distance_meters(row.location, location) > 75:
        return None
    return row


def membership_for_name(name):
    name = name.lower()
    if "costco" in name:
        return "costco"
    if "sam's club" in name or "sams club" in name:
        return "sams_club"
    return None


def located_inventory_match(inventory, quote):
    """A source with verified coordinates may omit state or street direction.

    Require the same numbered street/city/ZIP, one matching name, and <=25m.
    Explicit conflicting states or directions never qualify for this fallback.
    Address-only GasBuddy quotes continue to require the full strict crosswalk.
    """
    strict = inventory_match(inventory, quote.address, quote.location)
    if strict is not None:
        return strict
    address = normalized_address(quote.address)
    if not address or re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", address):
        return None
    if not re.match(r"^\d+\s+", address) or not re.search(r"\b\d{5}(?:-\d{4})?\s*$", address):
        return None

    def key(value):
        value = re.sub(r"\b[A-Z]{2}(?=\s+\d{5}(?:-\d{4})?\s*$)", "", normalized_address(value))
        value = re.sub(r"^(\d+\s+)(?:[NSEW]|North|South|East|West)\s+", r"\1", value, flags=re.IGNORECASE)
        return address_key(value)

    direction = re.match(r"^\d+\s+([NSEW]|North|South|East|West)\s+", address, re.IGNORECASE)
    aliases = {"north":"n", "south":"s", "east":"e", "west":"w"}
    name = re.sub(r"[^a-z0-9]", "", quote.name.lower())
    matches = []
    for row in inventory:
        other_direction = re.match(r"^\d+\s+([NSEW]|North|South|East|West)\s+", row.address or "", re.IGNORECASE)
        if direction and other_direction:
            a, b = direction[1].lower(), other_direction[1].lower()
            if aliases.get(a, a) != aliases.get(b, b):
                continue
        other_name = re.sub(r"[^a-z0-9]", "", row.name.lower())
        if name == other_name and key(address) == key(row.address) and distance_meters(row.location, quote.location) <= 25:
            matches.append(row)
    return matches[0] if len(matches) == 1 else None
