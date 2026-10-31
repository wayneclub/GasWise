export type VehicleArchetype =
  | 'coupe'
  | 'convertible'
  | 'sedan'
  | 'suv'
  | 'truck'
  | 'hatchback'
  | 'wagon'
  | 'van'

/**
 * Infer the vehicle's body archetype from its make, model, trim, or label string.
 * Used to automatically render a clean, high-precision silhouette thumbnail.
 */
export function inferVehicleArchetype(text?: string | null): VehicleArchetype {
  if (!text) return 'sedan'
  const s = text.toLowerCase()

  // 1. Convertible / Roadster / Spyder
  if (
    /\b(convertible|cabriolet|roadster|spider|spyder|drophead|cabrio|miata|boxster)\b/.test(s)
  ) {
    return 'convertible'
  }

  // 2. Coupe / 2-Door / Fastback
  if (
    /\b(coupe|2dr|2-door|gt coupe|cayman|brz|gr86|mustang|camaro|challenger|supra|lc\s?500|rc\s?350|corvette)\b/.test(s) ||
    /\b[ce]\d{3}\s+coupe\b/.test(s) ||
    /\b[24]\d{2}i\s+coupe\b/.test(s)
  ) {
    return 'coupe'
  }

  // 3. Truck / Pickup
  if (
    /\b(truck|pickup|f-?150|f-?250|f-?350|silverado|ram\s+1500|ram\s+2500|sierra|tacoma|tundra|ranger|colorado|canyon|titan|frontier|gladiator|cybertruck|rivian r1t|maverick|ridgeline)\b/.test(s)
  ) {
    return 'truck'
  }

  // 4. Van / Minivan
  if (
    /\b(van|minivan|sienna|odyssey|pacifica|carnival|caravan|transit|sprinter|metris|nv200|promaster)\b/.test(s)
  ) {
    return 'van'
  }

  // 5. Wagon / Estate
  if (
    /\b(wagon|avant|allroad|touring|estate|sportbrake|cross country|v60|v90)\b/.test(s)
  ) {
    return 'wagon'
  }

  // 6. Hatchback
  if (
    /\b(hatchback|hatch|5dr|5-door|golf|gti|fit|yaris|prius|leaf|bolt|mini cooper|fiesta|focus hatch|corolla hatch|mazda3 hatch|civic hatch|ioniq|i3|veloster)\b/.test(s)
  ) {
    return 'hatchback'
  }

  // 7. SUV / Crossover
  if (
    /\b(suv|crossover|sav|cuv|cr-?v|rav4|cx-?\d+|model y|model x|rx\s?\d+|gx\s?\d+|lx\s?\d+|glc|gle|gls|gla|glb|g-class|x1|x3|x5|x7|q3|q5|q7|q8|cherokee|grand cherokee|wrangler|explorer|expedition|tahoe|suburban|yukon|escalade|highlander|4runner|sequoia|land cruiser|telluride|palisade|sportage|sorento|tucson|santa fe|outback|forester|crosstrek|ascent|pilot|passport|hr-v|equinox|traverse|blazer|rogue|pathfinder|armada|durango|tiguan|atlas|macan|cayenne|urus|dbx|defender|discovery|range rover)\b/.test(s)
  ) {
    return 'suv'
  }

  // 8. Sedan
  if (
    /\b(sedan|4dr|4-door|saloon|camry|corolla|accord|civic|altima|maxima|sentra|optima|sonata|elantra|k5|model 3|model s|c300|e300|e350|e450|s500|s580|330i|530i|540i|740i|a3|a4|a6|a8|es\s?350|is\s?300|is\s?350|ls\s?500|genesis g70|genesis g80|passat|jetta|arteon|malibu|impala|fusion|charger|chrysler 300)\b/.test(s)
  ) {
    return 'sedan'
  }

  return 'sedan'
}
