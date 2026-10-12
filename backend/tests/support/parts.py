from datetime import UTC, datetime

from gaswise.contracts.vehicles import VinDecoded

URL = "https://www.amazon.com/Mann-Filter/dp/B019IPTB0W/ref=search?q=tracking"

ROW = dict(
    vehicleMake="MERCEDES-BENZ",
    vehicleName="E 400 4Matic",
    modelSeriesName="E-Class (A/C238)",
    engineCode="M276.823",
    ccm="2996",
    vehicleManufacturedFrom="2016-06-01",
    vehicleManufacturedTo="9999-12-31",
    serialNumberRange="",
)


def decoded(**changes):
    return VinDecoded(
        vin_masked="*************0000",
        fetched_at=datetime.now(UTC),
        check_digit_matches=True,
        error_codes=["0"],
        year=2018,
        make="MERCEDES-BENZ",
        model="E-Class",
        trim="E400",
        engine_liters=3,
        series="C238",
        **changes,
    )


class Decoder:
    async def decode(self, query):
        return decoded(engine_model="M276.823", drive="AWD")


def catalog_html():
    from urllib.parse import quote, urlencode

    return (
        '<h1>HU 7025 z</h1><a data-g-binding-params="' + quote("?" + urlencode(ROW), safe="") + '">E400</a>'
    )


def amazon_html():
    return (
        '<span id="productTitle">Mann Filter HU 7025 z Oil Filter</span>'
        '<input name="ASIN" value="B019IPTB0W"><table class="prodDetTable">'
        "<tr><th>ASIN</th><td>B019IPTB0W</td></tr>"
        "<tr><th>Brand Name</th><td>Mann Filter</td></tr>"
        "<tr><th>Manufacturer Part Number</th><td>HU7025Z</td></tr></table>"
    )
