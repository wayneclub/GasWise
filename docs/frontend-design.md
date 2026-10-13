# GasWise frontend design

The existing warm ivory, sage, Geist typography, 20px container radii and 14px
control radii remain the product foundation. Keep shared control dimensions,
responsive grouping and explicit payment/source semantics.

## Taste reference and Liquid Glass override

Reference: https://github.com/Leonxlnx/taste-skill/tree/c924fad1a79c7d70a04bcc8c415b593e9928ad8a/skills/taste-skill

The current `design-taste-frontend` skill targets public websites and explicitly
excludes app screens. Its house rules also prohibit glass. GasWise uses its
principles of deliberate typography, consistent spacing, honest content and
visual review as a reference; this is not strict conformance to that skill.
Liquid Glass is an explicit user-requested exception. Marketing hero, imagery
and motion quotas do not apply to this working application.

## Material boundaries

- `liquid-nav`: sticky navigation with a filled selected tab.
- `liquid-panel`: fuel planning and preferences surfaces.
- `liquid-control`, `liquid-segment`, `liquid-selection`: shared controls with
  restrained highlights; nested controls do not add backdrop filters.
- `liquid-sheet`: native modal sheet; its heading stays opaque for legibility.
- Prices, source status, rankings and station content retain their data surfaces.

Material values live in `frontend/src/index.css`. Glass starts from an opaque
fallback and adds blur only through feature detection. Reduced transparency
disables blur, reduced motion removes transitions, and forced colors keeps an
explicit selected-tab outline. Do not animate blur or add decorative refraction
filters to data-heavy lists.

## Validation

Use the frontend build, lint and existing tests, then inspect actual browser
rendering and overflow at narrow and desktop widths. Keep API contracts and
ranking behavior independent of presentation changes. A style check intended
for marketing pages cannot certify this application's accessibility or visual
quality.
