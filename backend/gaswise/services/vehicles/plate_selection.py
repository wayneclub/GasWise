"""Plate lookup feeds the same conservative VIN/EPA configuration resolver."""

from datetime import UTC, datetime

from gaswise.contracts.vehicles import PlateResolution, VinResolution
from gaswise.domain.ports import ProviderError
from gaswise.services.vehicles.selection import compact


class PlateSelector:
    def __init__(self, provider, vin_selector):
        self.provider, self.vin_selector = provider, vin_selector

    async def resolve(self, request):
        vin, make, model = await self.provider.vin(request)
        decoded = await self.vin_selector.decoder.decode(vin)
        if decoded.make is not None and compact(decoded.make) != compact(make):
            raise ProviderError("plate_vin_vehicle_mismatch")
        # The two catalogs can use different model labels. Require confirmation on
        # disagreement, even if the VIN alone would have produced one candidate.
        names = {compact(value) for value in (decoded.model, decoded.series, decoded.trim) if value}
        if names and compact(model) not in names and set(decoded.error_codes) == {"0"}:
            result = VinResolution(
                decoded=decoded,
                status="needs_input",
                question="車牌資料與 VIN 的型號名稱不一致，請以 VIN 或文字選車確認。",
                upstream_calls={"nhtsa_decode": 1, "epa_lookup": 0},
            )
        else:
            result = await self.vin_selector.resolve_decoded(vin, decoded)
        result.upstream_calls["plate_lookup"] = 1
        if getattr(self.provider, "source_id", None) == "autozone":
            result.warnings.append(
                "AutoZone does not echo plate/state; identity is linked by the submitted request only."
            )
        result.warnings.append(
            "Plate-to-VIN records may lag plate transfers; confirm the returned vehicle before saving it."
        )
        masked = (
            "*" * len(request.plate)
            if len(request.plate) <= 2
            else "*" * (len(request.plate) - 2) + request.plate[-2:]
        )
        return PlateResolution(
            plate_masked=masked,
            source=getattr(self.provider, "source_id", "vehicle_databases"),
            source_make=make,
            source_model=model,
            source_year=vin.model_year,
            state=request.state,
            fetched_at=datetime.now(UTC),
            resolution=result,
        )
