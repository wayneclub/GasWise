export type VehicleArchetype =
  | 'coupe'
  | 'convertible'
  | 'sedan'
  | 'suv'
  | 'truck'
  | 'hatchback'
  | 'wagon'
  | 'van'

export type VehicleSilhouette =
  | 'e_class_coupe' // Mercedes E-Class Coupe (curved pillarless greenhouse)
  | 'muscle_coupe' // Mustang / Camaro / Challenger
  | 'porsche_coupe' // 911 / Cayman / Carrera
  | 'tesla_sedan' // Tesla Model 3 / Model S flush aero fastback
  | 'executive_sedan' // Camry / Accord / Civic / C-Class / 3-Series
  | 'crossover_suv' // RAV4 / CR-V / Model Y / GLC / RX350
  | 'boxy_suv' // G-Class / Wrangler / Bronco / Defender
  | 'pickup_truck' // F-150 / Silverado / Tacoma / Ram
  | 'cybertruck' // Tesla Cybertruck geometric profile
  | 'roadster_convertible' // Miata / Z4 / Boxster / Spider
  | 'hatchback_golf' // Golf / GTI / Fit / Mini Cooper
  | 'aero_hatch_prius' // Prius / Ioniq / Leaf
  | 'wagon_estate' // Outback / Allroad / V60 / Avant
  | 'minivan' // Sienna / Odyssey / Pacifica

export interface VehicleColorPreset {
  id: string
  name: string
  hex: string
  labelZh: string
  labelEn: string
}

export const VEHICLE_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'obsidian', name: 'Obsidian Black', hex: '#1e293b', labelZh: '曜石黑', labelEn: 'Obsidian Black' },
  { id: 'white', name: 'Pearl White', hex: '#f8fafc', labelZh: '珍珠白', labelEn: 'Pearl White' },
  { id: 'grey', name: 'Nardo Grey', hex: '#64748b', labelZh: '水泥灰', labelEn: 'Nardo Grey' },
  { id: 'silver', name: 'Liquid Silver', hex: '#94a3b8', labelZh: '液態銀', labelEn: 'Liquid Silver' },
  { id: 'blue', name: 'Deep Metallic Blue', hex: '#1d4ed8', labelZh: '金屬藍', labelEn: 'Deep Metallic Blue' },
  { id: 'red', name: 'Soul Red', hex: '#dc2626', labelZh: '烈焰紅', labelEn: 'Soul Red' },
  { id: 'green', name: 'Racing Green', hex: '#15803d', labelZh: '英倫綠', labelEn: 'Racing Green' },
  { id: 'gold', name: 'Champagne Gold', hex: '#d97706', labelZh: '香檳金', labelEn: 'Champagne Gold' },
  { id: 'orange', name: 'Sunset Orange', hex: '#ea580c', labelZh: '熔岩橘', labelEn: 'Sunset Orange' },
  { id: 'purple', name: 'Midnight Purple', hex: '#7e22ce', labelZh: '魅夜紫', labelEn: 'Midnight Purple' },
]

export const SILHOUETTE_TO_ARCHETYPE: Record<VehicleSilhouette, VehicleArchetype> = {
  e_class_coupe: 'coupe',
  muscle_coupe: 'coupe',
  porsche_coupe: 'coupe',
  tesla_sedan: 'sedan',
  executive_sedan: 'sedan',
  crossover_suv: 'suv',
  boxy_suv: 'suv',
  pickup_truck: 'truck',
  cybertruck: 'truck',
  roadster_convertible: 'convertible',
  hatchback_golf: 'hatchback',
  aero_hatch_prius: 'hatchback',
  wagon_estate: 'wagon',
  minivan: 'van',
}

/**
 * Infer the detailed real vehicle silhouette profile based on label / make / model text.
 */
export function inferVehicleSilhouette(text?: string | null): VehicleSilhouette {
  if (!text) return 'executive_sedan'
  const s = text.toLowerCase()

  // 1. Cybertruck
  if (/\bcybertruck\b/.test(s)) {
    return 'cybertruck'
  }

  // 2. Mercedes E-Class / C-Class Coupe (and German pillarless coupes)
  if (
    /\b(e\s?400|e\s?450|e\s?350|c\s?300|c\s?400|c\s?43|c\s?63|e-?class|c-?class|c238|c205)\b.*\bcoupe\b/.test(s) ||
    /\bmercedes.*coupe\b/.test(s) ||
    /\bbenz.*coupe\b/.test(s)
  ) {
    return 'e_class_coupe'
  }

  // 3. American Muscle Coupe
  if (/\b(mustang|camaro|challenger|corvette)\b/.test(s)) {
    return 'muscle_coupe'
  }

  // 4. Porsche / Rear-engine Sports Coupe
  if (/\b(porsche|911|cayman|carrera|taycan)\b/.test(s)) {
    return 'porsche_coupe'
  }

  // 5. Roadster / Compact Convertible
  if (
    /\b(miata|mx-?5|roadster|spider|spyder|z4|slk|boxster|s2000|drophead|convertible|cabriolet|cabrio)\b/.test(s)
  ) {
    return 'roadster_convertible'
  }

  // 6. Boxy / Rugged Off-road SUV
  if (
    /\b(g-?class|g\s?550|g\s?63|gwagen|wrangler|bronco|defender|4runner|jimny|fj\s?cruiser)\b/.test(s)
  ) {
    return 'boxy_suv'
  }

  // 7. Pickup Truck
  if (
    /\b(truck|pickup|f-?150|f-?250|f-?350|silverado|ram\s+1500|ram\s+2500|sierra|tacoma|tundra|ranger|colorado|canyon|gladiator|titan|frontier|maverick|ridgeline)\b/.test(s)
  ) {
    return 'pickup_truck'
  }

  // 8. Aerodynamic Wedge Hatch (Prius, Ioniq, Leaf)
  if (/\b(prius|ioniq|insight|leaf|bolt\s?ev)\b/.test(s)) {
    return 'aero_hatch_prius'
  }

  // 9. Classic Hatchback (Golf, GTI, Fit, Yaris, Mini)
  if (
    /\b(golf|gti|fit|yaris|mini\s+cooper|cooper|fiesta|focus\s+hatch|corolla\s+hatch|civic\s+hatch|hatchback|hatch|5dr|5-door)\b/.test(s)
  ) {
    return 'hatchback_golf'
  }

  // 10. Station Wagon / Adventure Estate
  if (
    /\b(outback|allroad|v60|v90|avant|touring|wagon|estate|sportbrake|cross\s+country)\b/.test(s)
  ) {
    return 'wagon_estate'
  }

  // 11. Minivan / Passenger Van
  if (
    /\b(van|minivan|sienna|odyssey|pacifica|carnival|caravan|transit|sprinter|metris)\b/.test(s)
  ) {
    return 'minivan'
  }

  // 12. Tesla / Aerodynamic EV Sedan
  if (/\b(model\s+3|model\s+s|polestar|lucid)\b/.test(s)) {
    return 'tesla_sedan'
  }

  // 13. Other Coupe (general 2-door)
  if (/\b(coupe|2dr|2-door|brz|gr86|supra|lc\s?500|rc\s?350)\b/.test(s)) {
    return 'e_class_coupe'
  }

  // 14. Crossover SUV (RAV4, CR-V, Model Y, GLC, etc.)
  if (
    /\b(suv|crossover|sav|cuv|cr-?v|rav4|cx-?\d+|model\s+[yx]|rx\s?\d+|glc|gle|gls|gla|glb|x1|x3|x5|x7|q3|q5|q7|q8|cherokee|explorer|tahoe|suburban|yukon|escalade|highlander|telluride|palisade|sportage|sorento|tucson|santa\s+fe|forester|crosstrek|ascent|pilot|passport|hr-v|equinox|traverse|blazer|rogue|pathfinder|armada|durango|tiguan|atlas|macan|cayenne|urus)\b/.test(s)
  ) {
    return 'crossover_suv'
  }

  // 15. Default: Executive Sedan
  return 'executive_sedan'
}

/**
 * Infer the vehicle's body archetype from its make, model, trim, or label string.
 */
export function inferVehicleArchetype(text?: string | null): VehicleArchetype {
  const silhouette = inferVehicleSilhouette(text)
  return SILHOUETTE_TO_ARCHETYPE[silhouette]
}
