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

export const MERCEDES_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'white', name: 'Polar White (149)', hex: '#f8fafc', labelZh: '極地白 (149)', labelEn: 'Polar White (149)' },
  { id: 'obsidian', name: 'Obsidian Black (197)', hex: '#1a1f2c', labelZh: '曜石黑 (197)', labelEn: 'Obsidian Black (197)' },
  { id: 'grey', name: 'Selenite Grey (992)', hex: '#525a65', labelZh: '月光石灰 (992)', labelEn: 'Selenite Grey (992)' },
  { id: 'silver', name: 'Iridium Silver (775)', hex: '#a8b0b8', labelZh: '銥銀 (775)', labelEn: 'Iridium Silver (775)' },
  { id: 'blue', name: 'Lunar Blue (893)', hex: '#1b2a47', labelZh: '月藍 (893)', labelEn: 'Lunar Blue (893)' },
  { id: 'red', name: 'designo Cardinal Red (996)', hex: '#7a1c27', labelZh: '風情紅 (996)', labelEn: 'Cardinal Red (996)' },
]

export const TESLA_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'pearl_white', name: 'Pearl White Multi-Coat', hex: '#f8fafc', labelZh: '珍珠白', labelEn: 'Pearl White Multi-Coat' },
  { id: 'solid_black', name: 'Solid Black', hex: '#0f172a', labelZh: '純黑', labelEn: 'Solid Black' },
  { id: 'deep_blue', name: 'Deep Blue Metallic', hex: '#1e3a8a', labelZh: '深藍金屬漆', labelEn: 'Deep Blue Metallic' },
  { id: 'stealth_grey', name: 'Stealth Grey', hex: '#475569', labelZh: '隱形灰', labelEn: 'Stealth Grey' },
  { id: 'ultra_red', name: 'Ultra Red', hex: '#991b1b', labelZh: '烈焰紅', labelEn: 'Ultra Red' },
  { id: 'quicksilver', name: 'Quicksilver', hex: '#94a3b8', labelZh: '閃電銀', labelEn: 'Quicksilver' },
]

export const TOYOTA_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'wind_chill_pearl', name: 'Wind Chill Pearl / Super White', hex: '#f8fafc', labelZh: '極光白 / 珍珠白', labelEn: 'Wind Chill Pearl' },
  { id: 'midnight_black', name: 'Midnight Black Metallic', hex: '#111827', labelZh: '午夜黑', labelEn: 'Midnight Black Metallic' },
  { id: 'magnetic_gray', name: 'Magnetic Gray Metallic', hex: '#4b5563', labelZh: '磁性灰', labelEn: 'Magnetic Gray Metallic' },
  { id: 'celestial_silver', name: 'Celestial Silver Metallic', hex: '#cbd5e1', labelZh: '銀河銀', labelEn: 'Celestial Silver Metallic' },
  { id: 'blueprint', name: 'Blueprint / Cavalry Blue', hex: '#1d4ed8', labelZh: '藍圖深藍', labelEn: 'Blueprint' },
  { id: 'ruby_flare', name: 'Ruby Flare Pearl', hex: '#991b1b', labelZh: '烈焰紅', labelEn: 'Ruby Flare Pearl' },
  { id: 'army_green', name: 'Army Green', hex: '#3f4f3e', labelZh: '軍裝綠', labelEn: 'Army Green' },
]

export const BMW_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'alpine_white', name: 'Alpine White (300)', hex: '#f8fafc', labelZh: '高山白 (300)', labelEn: 'Alpine White (300)' },
  { id: 'black_sapphire', name: 'Black Sapphire Metallic (475)', hex: '#0f172a', labelZh: '藍寶石黑 (475)', labelEn: 'Black Sapphire (475)' },
  { id: 'skyscraper_grey', name: 'Skyscraper Grey Metallic (C4W)', hex: '#4b5563', labelZh: '摩天樓灰 (C4W)', labelEn: 'Skyscraper Grey (C4W)' },
  { id: 'brooklyn_grey', name: 'Brooklyn Grey Metallic (C4P)', hex: '#94a3b8', labelZh: '布魯克林灰 (C4P)', labelEn: 'Brooklyn Grey (C4P)' },
  { id: 'portimao_blue', name: 'Portimao Blue Metallic (C31)', hex: '#1d4ed8', labelZh: '波爾蒂芒藍 (C31)', labelEn: 'Portimao Blue (C31)' },
  { id: 'isle_of_man_green', name: 'Isle of Man Green (C4G)', hex: '#166534', labelZh: '曼島綠 (C4G)', labelEn: 'Isle of Man Green (C4G)' },
  { id: 'melbourne_red', name: 'Melbourne Red Metallic (A75)', hex: '#991b1b', labelZh: '墨爾本紅 (A75)', labelEn: 'Melbourne Red (A75)' },
]

export const PORSCHE_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'white', name: 'White (0Q)', hex: '#ffffff', labelZh: '純白 (0Q)', labelEn: 'White (0Q)' },
  { id: 'black', name: 'Black (A1)', hex: '#0f172a', labelZh: '純黑 (A1)', labelEn: 'Black (A1)' },
  { id: 'guards_red', name: 'Guards Red (84A)', hex: '#b91c1c', labelZh: '衛紅 (84A)', labelEn: 'Guards Red (84A)' },
  { id: 'racing_yellow', name: 'Racing Yellow (1S1)', hex: '#eab308', labelZh: '競速黃 (1S1)', labelEn: 'Racing Yellow (1S1)' },
  { id: 'gentian_blue', name: 'Gentian Blue Metallic (1A)', hex: '#1e3a8a', labelZh: '龍膽藍 (1A)', labelEn: 'Gentian Blue Metallic' },
  { id: 'gt_silver', name: 'GT Silver Metallic (M7Z)', hex: '#94a3b8', labelZh: 'GT銀 (M7Z)', labelEn: 'GT Silver Metallic' },
  { id: 'chalk', name: 'Chalk / Crayon (3H)', hex: '#d6d3d1', labelZh: '蠟灰 (3H)', labelEn: 'Chalk / Crayon (3H)' },
  { id: 'python_green', name: 'Python Green (3C)', hex: '#15803d', labelZh: '蟒蛇綠 (3C)', labelEn: 'Python Green (3C)' },
]

export const FORD_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'oxford_white', name: 'Oxford White (YZ)', hex: '#f8fafc', labelZh: '牛津白 (YZ)', labelEn: 'Oxford White (YZ)' },
  { id: 'agate_black', name: 'Agate Black Metallic (UM)', hex: '#111827', labelZh: '瑪瑙黑 (UM)', labelEn: 'Agate Black (UM)' },
  { id: 'carbonized_gray', name: 'Carbonized Gray Metallic (M7)', hex: '#374151', labelZh: '碳化灰 (M7)', labelEn: 'Carbonized Gray (M7)' },
  { id: 'iconic_silver', name: 'Iconic Silver Metallic (JS)', hex: '#9ca3af', labelZh: '標誌銀 (JS)', labelEn: 'Iconic Silver (JS)' },
  { id: 'atlas_blue', name: 'Atlas Blue Metallic (B3)', hex: '#1d4ed8', labelZh: '阿特拉斯藍 (B3)', labelEn: 'Atlas Blue (B3)' },
  { id: 'rapid_red', name: 'Rapid Red Metallic (D4)', hex: '#991b1b', labelZh: '極速紅 (D4)', labelEn: 'Rapid Red (D4)' },
  { id: 'grabber_blue', name: 'Grabber Blue (AE)', hex: '#38bdf8', labelZh: '掠奪者藍 (AE)', labelEn: 'Grabber Blue (AE)' },
]

export const HONDA_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'platinum_white', name: 'Platinum White Pearl (NH-883P)', hex: '#f8fafc', labelZh: '白金白 (NH-883P)', labelEn: 'Platinum White Pearl' },
  { id: 'crystal_black', name: 'Crystal Black Pearl (NH-731P)', hex: '#111827', labelZh: '水晶黑 (NH-731P)', labelEn: 'Crystal Black Pearl' },
  { id: 'meteorite_gray', name: 'Meteorite Gray Metallic (NH-904M)', hex: '#475569', labelZh: '隕石灰 (NH-904M)', labelEn: 'Meteorite Gray Metallic' },
  { id: 'lunar_silver', name: 'Lunar Silver Metallic (NH-830M)', hex: '#94a3b8', labelZh: '月光銀 (NH-830M)', labelEn: 'Lunar Silver Metallic' },
  { id: 'still_night', name: 'Still Night Pearl (B-575P)', hex: '#1d4ed8', labelZh: '寂夜藍 (B-575P)', labelEn: 'Still Night Pearl' },
  { id: 'radiant_red', name: 'Radiant Red Metallic (R-569M)', hex: '#991b1b', labelZh: '燦爛紅 (R-569M)', labelEn: 'Radiant Red Metallic' },
  { id: 'sonic_gray', name: 'Sonic Gray Pearl (NH-877P)', hex: '#64748b', labelZh: '音速灰 (NH-877P)', labelEn: 'Sonic Gray Pearl' },
]

export const UNIVERSAL_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'pearl_white', name: 'Pearl White', hex: '#f8fafc', labelZh: '珍珠白', labelEn: 'Pearl White' },
  { id: 'tuxedo_black', name: 'Tuxedo Black', hex: '#0f172a', labelZh: '尊爵黑', labelEn: 'Tuxedo Black' },
  { id: 'slate_grey', name: 'Slate Grey', hex: '#475569', labelZh: '冷冽灰', labelEn: 'Slate Grey' },
  { id: 'liquid_silver', name: 'Liquid Silver', hex: '#94a3b8', labelZh: '流光銀', labelEn: 'Liquid Silver' },
  { id: 'royal_blue', name: 'Royal Navy Blue', hex: '#1e3a8a', labelZh: '皇家藍', labelEn: 'Royal Navy Blue' },
  { id: 'crimson_red', name: 'Crimson Red', hex: '#991b1b', labelZh: '熱血紅', labelEn: 'Crimson Red' },
  { id: 'forest_green', name: 'Forest Green', hex: '#15803d', labelZh: '森林綠', labelEn: 'Forest Green' },
]

/**
 * Default color presets list for backward compatibility.
 */
export const VEHICLE_COLOR_PRESETS: VehicleColorPreset[] = MERCEDES_COLOR_PRESETS

/**
 * Returns authentic factory OEM color options matched to vehicle brand/label.
 */
export function getVehicleColorPresets(brandOrLabel?: string | null): VehicleColorPreset[] {
  if (!brandOrLabel) return UNIVERSAL_COLOR_PRESETS
  const s = brandOrLabel.toLowerCase()
  if (/\b(mercedes|benz|amg|maybach)\b/.test(s)) return MERCEDES_COLOR_PRESETS
  if (/\btesla\b/.test(s)) return TESLA_COLOR_PRESETS
  if (/\b(toyota|lexus|scion)\b/.test(s)) return TOYOTA_COLOR_PRESETS
  if (/\b(bmw|mini|rolls-royce)\b/.test(s)) return BMW_COLOR_PRESETS
  if (/\bporsche\b/.test(s)) return PORSCHE_COLOR_PRESETS
  if (/\b(ford|lincoln)\b/.test(s)) return FORD_COLOR_PRESETS
  if (/\b(honda|acura)\b/.test(s)) return HONDA_COLOR_PRESETS
  return UNIVERSAL_COLOR_PRESETS
}

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
    /\b(e\s?400|e\s?450|e\s?350|c\s?300|c\s?400|c\s?43|c\s?63|cle|e-?class|c-?class|c238|c205|4\s?series|8\s?series)\b.*\bcoupe\b/.test(s) ||
    /\b(cle|4\s?series\s+coupe|m4\b|m8\b)\b/.test(s) ||
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
    /\b(truck|pickup|f-?150|f-?250|f-?350|f-series|silverado|ram\s+1500|ram\s+2500|sierra|tacoma|tundra|ranger|colorado|canyon|gladiator|titan|frontier|maverick|ridgeline)\b/.test(s)
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
    /\b(suv|crossover|sav|cuv|cr-?v|rav4|cx-?\d+|model\s+[yx]|rx\s?\d+|glc|gle|gls|gla|glb|x1|x3|x5|x7|q3|q5|q7|q8|cherokee|explorer|tahoe|suburban|yukon|escalade|highlander|telluride|palisade|sportage|sorento|tucson|santa\s+fe|forester|crosstrek|ascent|pilot|passport|hr-v|equinox|traverse|blazer|rogue|pathfinder|armada|durango|tiguan|atlas|macan|cayenne|urus|kona|kicks|trax|terrain|acadia|compass|wagoneer)\b/.test(s)
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

function parseHexRgb(hex: string): [number, number, number] | null {
  const clean = hex.replace('#', '').trim()
  if (clean.length === 3) {
    return [
      parseInt(clean[0] + clean[0], 16),
      parseInt(clean[1] + clean[1], 16),
      parseInt(clean[2] + clean[2], 16),
    ]
  }
  if (clean.length === 6) {
    return [
      parseInt(clean.slice(0, 2), 16),
      parseInt(clean.slice(2, 4), 16),
      parseInt(clean.slice(4, 6), 16),
    ]
  }
  return null
}

export const VEHICLE_IMAGE_CACHE_VERSION = '20261104v2'

/**
 * Resolves color-accurate, transparent cut-out photograph for the 2018 Mercedes-Benz E400 Coupe.
 */
export function resolveE400ColorPhoto(color?: string | null): string {
  const versionParam = `?v=${VEHICLE_IMAGE_CACHE_VERSION}`
  if (!color || color === '#ffffff' || color === '#fff' || color === '#f8fafc') {
    return `/vehicles/2018_mercedes_benz_e400_coupe_white.png${versionParam}`
  }
  const norm = color.toLowerCase().trim()

  const PRESET_FILES: Record<string, string> = {
    '#f8fafc': 'white',
    '#ffffff': 'white',
    '#1a1f2c': 'obsidian',
    '#1e293b': 'obsidian',
    '#0f172a': 'obsidian',
    '#111827': 'obsidian',
    '#525a65': 'grey',
    '#64748b': 'grey',
    '#475569': 'grey',
    '#4b5563': 'grey',
    '#374151': 'grey',
    '#a8b0b8': 'silver',
    '#94a3b8': 'silver',
    '#cbd5e1': 'silver',
    '#9ca3af': 'silver',
    '#d6d3d1': 'silver',
    '#1b2a47': 'blue',
    '#1d4ed8': 'blue',
    '#1e3a8a': 'blue',
    '#7a1c27': 'red',
    '#dc2626': 'red',
    '#991b1b': 'red',
    '#b91c1c': 'red',
  }

  if (PRESET_FILES[norm]) {
    return `/vehicles/2018_mercedes_benz_e400_coupe_${PRESET_FILES[norm]}.png${versionParam}`
  }

  // Find closest preset match for custom color picker input
  const rgb = parseHexRgb(norm)
  if (!rgb) {
    return `/vehicles/2018_mercedes_benz_e400_coupe_white.png${versionParam}`
  }

  let bestPreset = 'obsidian'
  let minDistance = Infinity
  for (const preset of MERCEDES_COLOR_PRESETS) {
    const pRgb = parseHexRgb(preset.hex)
    if (!pRgb) continue
    const dist = (rgb[0] - pRgb[0]) ** 2 + (rgb[1] - pRgb[1]) ** 2 + (rgb[2] - pRgb[2]) ** 2
    if (dist < minDistance) {
      minDistance = dist
      bestPreset = preset.id
    }
  }
  return `/vehicles/2018_mercedes_benz_e400_coupe_${bestPreset}.png${versionParam}`
}

/**
 * Resolves color-accurate, transparent cut-out photograph for Tesla Model 3 and Model Y.
 */
export function resolveTeslaColorPhoto(model: 'model_3' | 'model_y', color?: string | null): string {
  const versionParam = `?v=${VEHICLE_IMAGE_CACHE_VERSION}`
  if (!color || color === '#ffffff' || color === '#fff' || color === '#f8fafc') {
    return `/vehicles/tesla_${model}_pearl_white.png${versionParam}`
  }
  const norm = color.toLowerCase().trim()

  const PRESET_FILES: Record<string, string> = {
    '#f8fafc': 'pearl_white',
    '#ffffff': 'pearl_white',
    '#0f172a': 'solid_black',
    '#111827': 'solid_black',
    '#1a1f2c': 'solid_black',
    '#1e293b': 'solid_black',
    '#1e3a8a': 'deep_blue',
    '#1b2a47': 'deep_blue',
    '#1d4ed8': 'deep_blue',
    '#475569': 'stealth_grey',
    '#525a65': 'stealth_grey',
    '#64748b': 'stealth_grey',
    '#4b5563': 'stealth_grey',
    '#374151': 'stealth_grey',
    '#991b1b': 'ultra_red',
    '#7a1c27': 'ultra_red',
    '#dc2626': 'ultra_red',
    '#b91c1c': 'ultra_red',
    '#94a3b8': model === 'model_y' ? 'quicksilver' : 'stealth_grey',
    '#a8b0b8': model === 'model_y' ? 'quicksilver' : 'stealth_grey',
    '#cbd5e1': model === 'model_y' ? 'quicksilver' : 'stealth_grey',
  }

  if (PRESET_FILES[norm]) {
    return `/vehicles/tesla_${model}_${PRESET_FILES[norm]}.png${versionParam}`
  }

  const rgb = parseHexRgb(norm)
  if (!rgb) {
    return `/vehicles/tesla_${model}_pearl_white.png${versionParam}`
  }

  let bestPreset = 'pearl_white'
  let minDistance = Infinity
  for (const preset of TESLA_COLOR_PRESETS) {
    if (model === 'model_3' && preset.id === 'quicksilver') continue
    const pRgb = parseHexRgb(preset.hex)
    if (!pRgb) continue
    const dist = (rgb[0] - pRgb[0]) ** 2 + (rgb[1] - pRgb[1]) ** 2 + (rgb[2] - pRgb[2]) ** 2
    if (dist < minDistance) {
      minDistance = dist
      bestPreset = preset.id
    }
  }
  return `/vehicles/tesla_${model}_${bestPreset}.png${versionParam}`
}

/**
 * Resolves an authentic vehicle photo URL if available or set.
 */
export function resolveVehiclePhoto(
  label?: string | null,
  customImageUrl?: string | null,
  color?: string | null,
): string | null {
  if (customImageUrl && customImageUrl.trim().length > 0) {
    const raw = customImageUrl.trim()
    // Support direct Carvana vehicle listing URLs
    const carvanaMatch = raw.match(/carvana\.com\/vehicle\/(\d+)/i)
    if (carvanaMatch) {
      const vehicleId = carvanaMatch[1]
      if (vehicleId === '4856325') {
        return resolveE400ColorPhoto(color)
      }
    }
    return raw
  }
  if (!label) return null
  const s = label.toLowerCase()
  if (
    (/\b(e\s?400|e\s?450|e\s?350)\b.*\bcoupe\b/i.test(s) || (/\b(mercedes|benz)\b/i.test(s) && /\bcoupe\b/i.test(s)))
  ) {
    return resolveE400ColorPhoto(color)
  }
  if ((/\btesla\b/i.test(s) && /\b(model\s*3|m3)\b/i.test(s)) || (/\bmodel\s*3\b/i.test(s) && !/\bmazda\b/i.test(s))) {
    return resolveTeslaColorPhoto('model_3', color)
  }
  if ((/\btesla\b/i.test(s) && /\b(model\s*y|my)\b/i.test(s)) || /\bmodel\s*y\b/i.test(s)) {
    return resolveTeslaColorPhoto('model_y', color)
  }
  return null
}
