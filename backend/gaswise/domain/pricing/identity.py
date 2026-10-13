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


HOUSE_NUMBER = re.compile(r"^\s*(\d+[A-Z]?)\s+([^,]+)", re.IGNORECASE)
ORDINALS = dict(zip(
    "first second third fourth fifth sixth seventh eighth ninth tenth".split(),
    "1st 2nd 3rd 4th 5th 6th 7th 8th 9th 10th".split(),
    strict=True,
))
STREET_NOISE = set(
    "n s e w ne nw se sw north south east west st street ave av avenue blvd boulevard rd road dr drive "
    "way hwy highway ln lane pl place ct court pkwy parkway cir circle ter terrace trl trail sq".split()
)


def street_parts(address):
    """House number plus distinctive street words; ignores direction, suffix and city spelling."""
    match = HOUSE_NUMBER.match(address or "")
    if match is None:
        return None, set()
    words = re.findall(r"[a-z0-9]+", match[2].lower())
    return match[1].lower(), {ORDINALS.get(word, word) for word in words} - STREET_NOISE


def site_match(inventory, quote, meters=60, site_meters=40):
    """Crosswalk a source that carries its own coordinates.

    Sources spell one forecourt differently ("1st"/"First", "W Sunset"/"Sunset",
    postal vs administrative city) and Google may list a station and its store as
    separate places. Require the same house number, a shared street word and
    nearby coordinates; every candidate must sit on one site. Never match by brand alone.
    A listing whose street line is not an address (a promotion slogan) needs the exact
    station name within 25m instead.
    """
    strict = inventory_match(inventory, quote.address, quote.location)
    if strict is not None or quote.location is None:
        return strict
    number, street = street_parts(quote.address)
    if number is None:
        name = re.sub(r"[^a-z0-9]", "", quote.name.lower())
        rows = [
            row for row in inventory
            if re.sub(r"[^a-z0-9]", "", row.name.lower()) == name
            and distance_meters(row.location, quote.location) <= 25
        ]
        return rows[0] if len(rows) == 1 else None
    if not street:
        return None
    rows = []
    for row in inventory:
        other_number, other_street = street_parts(row.address)
        if (
            other_number == number
            and street & other_street
            and distance_meters(row.location, quote.location) <= meters
        ):
            rows.append(row)
    if not rows or any(distance_meters(a.location, b.location) > site_meters for a in rows for b in rows):
        return None
    brand = next(iter(re.findall(r"[a-z0-9]+", quote.name.lower())), "")
    return min(
        rows,
        key=lambda row: (brand not in row.name.lower(), distance_meters(row.location, quote.location)),
    )
