"""Proven-disk coverage for capped, relevance-ranked station searches.

One website search lists one page of places for a viewport sized by its query
radius. Ranking favours nearby places but is not strictly nearest-first, and a
wide viewport skips near stations. So only a page that spills past its radius
(a short page, or one reaching beyond it) proves its query disk complete. A page
that fills up inside its radius proves nothing; its reach sets a smaller radius
for the next wave. Query points are H3 cell centres and radii come from a fixed
ladder, so nearby searches reuse the same cache entries.
"""

import math

import h3

from gaswise.contracts.common import Point
from gaswise.domain.pricing.comparison import distance_meters

RADIUS_STEPS = (800, 1600, 3200, 6400, 12800, 25600, 50000)
SHRINK = 0.6  # A page filled at reach d suggests a disk of ~0.6d holds well under one page.
# Live pages sometimes list 19 of 20 places with coordinates; only a clearly short page is sparse.
SHORT_PAGE = 0.75
# A wide viewport spreads its page thinly by relevance (Bakersfield: 19 places across 10km while
# GasBuddy listed 33 stations). Spilling past the radius proves the disk only for local viewports.
LOCAL_VIEWPORT = 3200


def step_at_most(meters):
    return max((step for step in RADIUS_STEPS if step <= meters), default=RADIUS_STEPS[0])


def grid_points(origin, radius):
    """H3 cell centres inside the disk, nearest first (~460m apart, ~1.2km past 16km)."""
    resolution = 8 if radius <= 16000 else 7
    edge = h3.average_hexagon_edge_length(resolution, "m")
    centre = h3.latlng_to_cell(origin.lat, origin.lng, resolution)
    points = []
    for cell in h3.grid_disk(centre, math.ceil(radius / (edge * 1.5)) + 1):
        lat, lng = h3.cell_to_latlng(cell)
        point = Point(lat=lat, lng=lng)
        if distance_meters(origin, point) <= radius:
            points.append(point)
    return sorted(points, key=lambda point: distance_meters(origin, point))


class Coverage:
    def __init__(self, origin, radius):
        self.origin, self.radius = origin, radius
        self.points = grid_points(origin, radius)
        self.proven = []  # (centre, metres proven complete)
        self.tried = set()  # (lat, lng, query radius)
        self.query_radius = step_at_most(radius)
        self.last_wave = []  # (share of a page inside the radius, spilled) since the previous wave

    def covered(self, point):
        return any(distance_meters(point, centre) <= reach for centre, reach in self.proven)

    def record(self, centre, query_radius, count, within, reach, page_size):
        """Apply one response (`within`: places inside the query disk); returns whether it proved the disk."""
        spilled = count <= page_size * SHORT_PAGE or (
            query_radius <= LOCAL_VIEWPORT and reach is not None and reach > query_radius
        )
        self.last_wave.append((within / page_size, spilled))
        if spilled:
            self.proven.append((centre, query_radius))
            return True
        if query_radius <= RADIUS_STEPS[0]:
            # Densest blocks: the finest query cannot spill, keep what the page reached.
            self.proven.append((centre, min(query_radius, reach or 0)))
            return False
        # One step per wave: a single wide page's reach is not a reliable density estimate.
        narrower = [step for step in RADIUS_STEPS if step < min(self.query_radius, query_radius)]
        self.query_radius = max(narrower[-1] if narrower else RADIUS_STEPS[0],
                                step_at_most((reach or 0) * SHRINK))
        return False

    def wave(self, width):
        """Nearest unproven points at the current radius, spaced so their disks just overlap.

        A wave whose pages all spilled at most half full was sparse: widen one step.
        """
        if self.last_wave and all(spilled and fill <= 0.5 for fill, spilled in self.last_wave):
            wider = [step for step in RADIUS_STEPS if self.query_radius < step <= self.radius]
            self.query_radius = wider[0] if wider else self.query_radius
        self.last_wave = []
        radius, batch = self.query_radius, []
        for point in self.points:
            if len(batch) >= width:
                break
            if (point.lat, point.lng, radius) in self.tried or self.covered(point):
                continue
            if all(distance_meters(point, other) > radius * 1.5 for other in batch):
                batch.append(point)
        self.tried.update((point.lat, point.lng, radius) for point in batch)
        return batch, radius

    def fraction(self):
        if not self.points:
            return 1.0
        return sum(self.covered(point) for point in self.points) / len(self.points)
