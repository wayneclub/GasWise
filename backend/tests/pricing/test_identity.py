from gaswise.contracts.common import Point
from gaswise.contracts.sources import MapsWebStation
from gaswise.domain.pricing.identity import inventory_match, membership_for_name, site_match

ADDRESS = "1516 S Main St, Los Angeles, CA 90015"


def station(place_id="one", address=ADDRESS):
    return MapsWebStation(
        place_id=place_id,
        name="Shell",
        address=address,
        location=Point(lat=34, lng=-118),
        distance_meters=0,
        available_fuel_types=[],
    )


def test_ambiguous_same_address_does_not_create_crosswalk():
    assert inventory_match([station(), station("two")], ADDRESS) is None


def test_partial_or_different_address_does_not_create_crosswalk():
    assert inventory_match([station()], "Shell") is None
    assert inventory_match([station()], ADDRESS.replace("1516", "1518")) is None
    assert inventory_match([station()], ADDRESS.replace("90015", "90016")) is None


def test_waze_coordinates_must_support_exact_address_match():
    assert inventory_match([station()], ADDRESS, Point(lat=35, lng=-118)) is None
    assert inventory_match([station()], ADDRESS, Point(lat=34.00001, lng=-118)).place_id == "one"


def test_punctuation_is_normalized_without_guessing_street_aliases():
    assert inventory_match([station()], "1516 S Main St Los Angeles CA 90015") is not None
    assert inventory_match([station()], ADDRESS.replace("St,", "Street,")) is None


def test_zip_plus_four_matches_zip_five_but_not_a_different_zip():
    assert inventory_match([station()], ADDRESS + "-1230") is not None
    assert inventory_match([station()], ADDRESS.replace("90015", "90016-1230")) is None


def test_warehouse_names_keep_membership_gate():
    assert membership_for_name("Costco Gasoline") == "costco"
    assert membership_for_name("Sam's Club Fuel Center") == "sams_club"
    assert membership_for_name("Shell") is None


def test_located_missing_state_crosswalk_is_unique_nearby_and_never_name_only():
    from types import SimpleNamespace

    from gaswise.contracts.common import Point
    from gaswise.domain.pricing.identity import located_inventory_match
    point = Point(lat=34.0277, lng=-118.2759)
    row = SimpleNamespace(name='Mobil', address='2620 S Figueroa St, Los Angeles, CA 90007', location=point)
    quote = SimpleNamespace(name='Mobil', address='2620 S Figueroa St Los Angeles 90007', location=point)
    assert located_inventory_match([row], quote) is row
    assert located_inventory_match([row,row], quote) is None
    quote.location = Point(lat=34.0287, lng=-118.2759)
    assert located_inventory_match([row], quote) is None
    quote.location = point
    quote.address = '2620 S Figueroa St, Los Angeles, NV 90007'
    assert located_inventory_match([row], quote) is None
    quote.address = '2620 N Figueroa St Los Angeles 90007'
    assert located_inventory_match([row], quote) is None
    quote.address = '2620 Figueroa St Los Angeles 90007'
    assert located_inventory_match([row], quote) is row
    quote.name = 'Shell'
    assert located_inventory_match([row], quote) is None


def place(place_id, name, address, lat, lng):
    return MapsWebStation(
        place_id=place_id, name=name, address=address, location=Point(lat=lat, lng=lng),
        distance_meters=0, available_fuel_types=[],
    )


def located_quote(name, address, lat, lng):
    from types import SimpleNamespace

    return SimpleNamespace(name=name, address=address, location=Point(lat=lat, lng=lng))


def test_site_match_accepts_same_forecourt_spelled_differently():
    # Real production pairs: ordinal words, dropped direction and postal vs administrative city.
    first = place("first", "Chevron", "1666 First Ave., San Diego, CA 92101", 32.7226, -117.1641)
    assert site_match([first], located_quote("Chevron", "1666 1st Ave, San Diego, CA 92101-3004", 32.7227, -117.1641)) is first
    sunset = place("sunset", "Shell", "5657 Sunset Blvd, Los Angeles, CA 90028", 34.0982, -118.3138)
    assert site_match([sunset], located_quote("Shell", "5657 W Sunset Blvd, Hollywood, CA 90028-8523", 34.0983, -118.3138)) is sunset


def test_site_match_resolves_station_and_store_listed_at_one_site():
    station_place = place("station", "Chevron ExtraMile Los Angeles", "525 W Washington Blvd, Los Angeles, CA 90015", 34.0345181, -118.2715411)
    store = place("store", "ExtraMile", "525 W Washington Blvd, Los Angeles, CA 90015", 34.0345074, -118.2715882)
    quote = located_quote("Chevron", "525 W Washington Blvd, Los Angeles, CA 90015-4109", 34.03452, -118.27156)
    assert site_match([store, station_place], quote) is station_place


def test_site_match_never_matches_by_proximity_or_brand_alone():
    quote = located_quote("Shell", "1516 S Main St, Los Angeles, CA 90015", 34, -118)
    other_number = place("a", "Shell", "1520 S Main St, Los Angeles, CA 90015", 34, -118)
    other_street = place("b", "Shell", "1516 Olive St, Los Angeles, CA 90015", 34, -118)
    far = place("c", "Shell", "1516 Main St, Los Angeles, CA 90015", 34.001, -118)
    assert site_match([other_number, other_street, far], quote) is None
    two_sites = [place("d", "Shell", "1516 Main St", 34.0003, -118), place("e", "Shell", "1516 Main St", 33.9997, -118)]
    assert site_match(two_sites, quote) is None
    unplaced = located_quote("Shell", "1516 Main St", 34, -118)
    unplaced.location = None
    assert site_match([place("f", "Shell", "1516 Main St", 34, -118)], unplaced) is None


def test_site_match_without_street_address_needs_exact_name_close_by():
    # GasBuddy production row whose street line is a promotion, 9m from the Google place.
    summit = place("summit", "Summit Gasoline", "3580 Sports Arena Blvd, San Diego, CA 92110", 32.7550, -117.2100)
    slogan = located_quote("Summit Gasoline", "CASH DISCOUNT DAILY!, Point Loma, CA 92110-4919", 32.75508, -117.2100)
    assert site_match([summit], slogan) is summit
    assert site_match([summit], located_quote("Summit", slogan.address, 32.75508, -117.2100)) is None
    assert site_match([summit], located_quote("Summit Gasoline", slogan.address, 32.7556, -117.2100)) is None
