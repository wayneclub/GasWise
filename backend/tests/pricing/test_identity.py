from gaswise.contracts.common import Point
from gaswise.contracts.sources import MapsWebStation
from gaswise.domain.pricing.identity import inventory_match, membership_for_name

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
