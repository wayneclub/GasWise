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

export const BMW_M4_F82_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'austin_yellow', name: 'Austin Yellow Metallic (B67)', hex: '#d2b134', labelZh: '奧斯汀黃 (B67)', labelEn: 'Austin Yellow Metallic' },
  { id: 'yas_marina_blue', name: 'Yas Marina Blue Metallic (B68)', hex: '#5c9dc0', labelZh: '亞斯碼頭藍 (B68)', labelEn: 'Yas Marina Blue Metallic' },
  { id: 'sakhir_orange', name: 'Sakhir Orange II Metallic (C1H)', hex: '#a8322d', labelZh: '薩基爾橙 (C1H)', labelEn: 'Sakhir Orange II Metallic' },
  { id: 'san_marino_blue', name: 'San Marino Blue Metallic (B51)', hex: '#1c3b72', labelZh: '聖馬利諾藍 (B51)', labelEn: 'San Marino Blue Metallic' },
  { id: 'mineral_grey', name: 'Mineral Grey Metallic (B39)', hex: '#484b50', labelZh: '礦石灰 (B39)', labelEn: 'Mineral Grey Metallic' },
  { id: 'black_sapphire', name: 'Black Sapphire Metallic (475)', hex: '#121417', labelZh: '藍寶石黑 (475)', labelEn: 'Black Sapphire Metallic' },
  { id: 'alpine_white', name: 'Alpine White (300)', hex: '#faf9fb', labelZh: '雪山白 (300)', labelEn: 'Alpine White' },
  { id: 'silverstone', name: 'Silverstone II Metallic (A29)', hex: '#b8c3cc', labelZh: '銀石銀 (A29)', labelEn: 'Silverstone II Metallic' },
  { id: 'mineral_white', name: 'Mineral White Metallic (A96)', hex: '#f0f0ee', labelZh: '礦石白 (A96)', labelEn: 'Mineral White Metallic' },
]

export const TOYOTA_RAV4_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'wind_chill_pearl', name: 'Wind Chill Pearl / Super White (089)', hex: '#f8fafc', labelZh: '極光珍珠白 (089)', labelEn: 'Wind Chill Pearl' },
  { id: 'midnight_black', name: 'Midnight Black Metallic (218)', hex: '#111827', labelZh: '午夜黑 (218)', labelEn: 'Midnight Black Metallic' },
  { id: 'magnetic_gray', name: 'Magnetic Gray Metallic (1G3)', hex: '#4b5563', labelZh: '磁性灰 (1G3)', labelEn: 'Magnetic Gray Metallic' },
  { id: 'silver_sky', name: 'Silver Sky Metallic (1D6)', hex: '#cbd5e1', labelZh: '天空銀 (1D6)', labelEn: 'Silver Sky Metallic' },
  { id: 'blueprint', name: 'Blueprint (8X8)', hex: '#1d4ed8', labelZh: '藍圖深藍 (8X8)', labelEn: 'Blueprint' },
  { id: 'ruby_flare', name: 'Ruby Flare Pearl (3T3)', hex: '#991b1b', labelZh: '尊爵紅 (3T3)', labelEn: 'Ruby Flare Pearl' },
  { id: 'lunar_rock', name: 'Lunar Rock (6X3)', hex: '#8b9788', labelZh: '岩石灰綠 / 月岩灰 (6X3)', labelEn: 'Lunar Rock' },
  { id: 'army_green', name: 'Army Green (6V7)', hex: '#3f4f3e', labelZh: '軍裝綠 (6V7)', labelEn: 'Army Green' },
  { id: 'cavalry_blue', name: 'Cavalry Blue (8W2)', hex: '#4b6b82', labelZh: '騎兵藍 (8W2)', labelEn: 'Cavalry Blue' },
]

export const FORD_MUSTANG_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'oxford_white', name: 'Oxford White (YZ)', hex: '#f8fafc', labelZh: '牛津白 (YZ)', labelEn: 'Oxford White' },
  { id: 'shadow_black', name: 'Shadow Black (G1)', hex: '#111827', labelZh: '暗影黑 (G1)', labelEn: 'Shadow Black' },
  { id: 'grabber_blue', name: 'Grabber Blue (AE)', hex: '#38bdf8', labelZh: '掠奪者藍 (AE)', labelEn: 'Grabber Blue' },
  { id: 'race_red', name: 'Race Red (PQ)', hex: '#dc2626', labelZh: '競技紅 (PQ)', labelEn: 'Race Red' },
  { id: 'twister_orange', name: 'Twister Orange (E3)', hex: '#ea580c', labelZh: '龍捲風橙 (E3)', labelEn: 'Twister Orange' },
  { id: 'velocity_blue', name: 'Velocity Blue (E7)', hex: '#1d4ed8', labelZh: '疾速藍 (E7)', labelEn: 'Velocity Blue' },
  { id: 'magnetic', name: 'Magnetic Metallic (J7)', hex: '#374151', labelZh: '磁石灰 (J7)', labelEn: 'Magnetic Metallic' },
  { id: 'iconic_silver', name: 'Iconic Silver (JS)', hex: '#9ca3af', labelZh: '標誌銀 (JS)', labelEn: 'Iconic Silver' },
]

export const PORSCHE_911_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'guards_red', name: 'Guards Red (84A)', hex: '#b91c1c', labelZh: '衛紅 (84A)', labelEn: 'Guards Red' },
  { id: 'racing_yellow', name: 'Racing Yellow (1S1)', hex: '#eab308', labelZh: '競速黃 (1S1)', labelEn: 'Racing Yellow' },
  { id: 'gt_silver', name: 'GT Silver Metallic (M7Z)', hex: '#94a3b8', labelZh: 'GT銀 (M7Z)', labelEn: 'GT Silver Metallic' },
  { id: 'gentian_blue', name: 'Gentian Blue Metallic (1A)', hex: '#1e3a8a', labelZh: '龍膽藍 (1A)', labelEn: 'Gentian Blue Metallic' },
  { id: 'chalk', name: 'Chalk / Crayon (3H)', hex: '#d6d3d1', labelZh: '蠟灰 (3H)', labelEn: 'Chalk / Crayon' },
  { id: 'white', name: 'White (0Q)', hex: '#ffffff', labelZh: '純白 (0Q)', labelEn: 'White' },
  { id: 'black', name: 'Black (A1)', hex: '#0f172a', labelZh: '純黑 (A1)', labelEn: 'Black' },
  { id: 'python_green', name: 'Python Green (3C)', hex: '#15803d', labelZh: '蟒蛇綠 (3C)', labelEn: 'Python Green' },
  { id: 'shark_blue', name: 'Shark Blue (D5C)', hex: '#0284c7', labelZh: '鯊魚藍 (D5C)', labelEn: 'Shark Blue' },
]

export const BMW_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'alpine_white', name: 'Alpine White (300)', hex: '#faf9fb', labelZh: '高山白 (300)', labelEn: 'Alpine White (300)' },
  { id: 'black_sapphire', name: 'Black Sapphire Metallic (475)', hex: '#121417', labelZh: '藍寶石黑 (475)', labelEn: 'Black Sapphire (475)' },
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

export const CHEVROLET_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'summit_white', name: 'Summit White (GAZ)', hex: '#f8fafc', labelZh: '高峰白 (GAZ)', labelEn: 'Summit White (GAZ)' },
  { id: 'black', name: 'Black (GBA)', hex: '#0f172a', labelZh: '極致黑 (GBA)', labelEn: 'Black (GBA)' },
  { id: 'sterling_gray', name: 'Sterling Gray Metallic (GXD)', hex: '#4b5563', labelZh: '斯特林灰 (GXD)', labelEn: 'Sterling Gray Metallic' },
  { id: 'radiant_red', name: 'Radiant Red Tintcoat (GNT)', hex: '#991b1b', labelZh: '耀石紅 (GNT)', labelEn: 'Radiant Red Tintcoat' },
  { id: 'riptide_blue', name: 'Riptide Blue Metallic (GJV)', hex: '#1d4ed8', labelZh: '激流藍 (GJV)', labelEn: 'Riptide Blue Metallic' },
  { id: 'cacti_green', name: 'Cacti Green (GNS)', hex: '#5b6f5d', labelZh: '仙人掌綠 (GNS)', labelEn: 'Cacti Green (GNS)' },
  { id: 'nitro_yellow', name: 'Nitro Yellow Metallic (GCP)', hex: '#eab308', labelZh: '硝基黃 (GCP)', labelEn: 'Nitro Yellow Metallic' },
]

export const HYUNDAI_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'atlas_white', name: 'Atlas White (SAW)', hex: '#f8fafc', labelZh: '阿特拉斯白 (SAW)', labelEn: 'Atlas White (SAW)' },
  { id: 'phantom_black', name: 'Phantom Black (NKA)', hex: '#0f172a', labelZh: '幻影黑 (NKA)', labelEn: 'Phantom Black (NKA)' },
  { id: 'portofino_gray', name: 'Portofino Gray (T2G)', hex: '#475569', labelZh: '波托菲諾灰 (T2G)', labelEn: 'Portofino Gray (T2G)' },
  { id: 'shimmering_silver', name: 'Shimmering Silver (R2T)', hex: '#cbd5e1', labelZh: '閃耀銀 (R2T)', labelEn: 'Shimmering Silver (R2T)' },
  { id: 'intense_blue', name: 'Intense Blue (YP5)', hex: '#1d4ed8', labelZh: '極致藍 (YP5)', labelEn: 'Intense Blue (YP5)' },
  { id: 'ultimate_red', name: 'Ultimate Red (R2P)', hex: '#991b1b', labelZh: '終極紅 (R2P)', labelEn: 'Ultimate Red (R2P)' },
  { id: 'amazon_gray', name: 'Amazon Gray (A2G)', hex: '#3f4f3e', labelZh: '亞馬遜綠灰 (A2G)', labelEn: 'Amazon Gray (A2G)' },
]

export const KIA_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'glacial_white', name: 'Glacial White Pearl (GWP)', hex: '#f8fafc', labelZh: '冰川白珍珠 (GWP)', labelEn: 'Glacial White Pearl' },
  { id: 'ebony_black', name: 'Ebony Black (EB)', hex: '#0f172a', labelZh: '烏木黑 (EB)', labelEn: 'Ebony Black (EB)' },
  { id: 'gravity_gray', name: 'Gravity Gray (KDG)', hex: '#475569', labelZh: '引力灰 (KDG)', labelEn: 'Gravity Gray (KDG)' },
  { id: 'everlasting_silver', name: 'Everlasting Silver (4SS)', hex: '#cbd5e1', labelZh: '恆久銀 (4SS)', labelEn: 'Everlasting Silver' },
  { id: 'sapphire_blue', name: 'Sapphire Blue (B3L)', hex: '#1e3a8a', labelZh: '藍寶石藍 (B3L)', labelEn: 'Sapphire Blue' },
  { id: 'dawning_red', name: 'Dawning Red (DRD)', hex: '#991b1b', labelZh: '黎明紅 (DRD)', labelEn: 'Dawning Red (DRD)' },
  { id: 'jungle_green', name: 'Jungle Green (JUG)', hex: '#2d4739', labelZh: '叢林綠 (JUG)', labelEn: 'Jungle Green (JUG)' },
  { id: 'wolf_gray', name: 'Wolf Gray (DWG)', hex: '#94a3b8', labelZh: '灰狼色 (DWG)', labelEn: 'Wolf Gray (DWG)' },
]

export const SUBARU_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'crystal_white', name: 'Crystal White Pearl (K1X)', hex: '#f8fafc', labelZh: '水晶白珍珠 (K1X)', labelEn: 'Crystal White Pearl' },
  { id: 'crystal_black', name: 'Crystal Black Silica (D4S)', hex: '#0f172a', labelZh: '水晶黑矽 (D4S)', labelEn: 'Crystal Black Silica' },
  { id: 'magnetite_gray', name: 'Magnetite Gray Metallic (P8Y)', hex: '#4b5563', labelZh: '磁鐵礦灰 (P8Y)', labelEn: 'Magnetite Gray Metallic' },
  { id: 'ice_silver', name: 'Ice Silver Metallic (G1U)', hex: '#cbd5e1', labelZh: '冰銀金屬漆 (G1U)', labelEn: 'Ice Silver Metallic' },
  { id: 'sapphire_blue', name: 'Sapphire Blue Pearl (WCH)', hex: '#1e3a8a', labelZh: '藍寶石藍 (WCH)', labelEn: 'Sapphire Blue Pearl' },
  { id: 'crimson_red', name: 'Crimson Red Pearl (M1Y)', hex: '#991b1b', labelZh: '深紅珍珠 (M1Y)', labelEn: 'Crimson Red Pearl' },
  { id: 'autumn_green', name: 'Autumn Green Metallic (G2U)', hex: '#3b4c3d', labelZh: '秋綠金屬漆 (G2U)', labelEn: 'Autumn Green Metallic' },
  { id: 'wr_blue', name: 'WR Blue Pearl (K7X)', hex: '#0284c7', labelZh: '拉力藍 (K7X)', labelEn: 'WR Blue Pearl (K7X)' },
]

export const NISSAN_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'glacier_white', name: 'Glacier White (QAK)', hex: '#f8fafc', labelZh: '冰川白 (QAK)', labelEn: 'Glacier White (QAK)' },
  { id: 'super_black', name: 'Super Black (KH3)', hex: '#0f172a', labelZh: '超級黑 (KH3)', labelEn: 'Super Black (KH3)' },
  { id: 'gun_metallic', name: 'Gun Metallic (KAD)', hex: '#4b5563', labelZh: '槍灰色 (KAD)', labelEn: 'Gun Metallic (KAD)' },
  { id: 'brilliant_silver', name: 'Brilliant Silver Metallic (K23)', hex: '#cbd5e1', labelZh: '璀璨銀 (K23)', labelEn: 'Brilliant Silver Metallic' },
  { id: 'deep_blue', name: 'Deep Blue Pearl (RAY)', hex: '#1e3a8a', labelZh: '深藍珍珠 (RAY)', labelEn: 'Deep Blue Pearl' },
  { id: 'scarlet_ember', name: 'Scarlet Ember Tintcoat (NBL)', hex: '#991b1b', labelZh: '緋紅 (NBL)', labelEn: 'Scarlet Ember Tintcoat' },
  { id: 'boulder_gray', name: 'Boulder Gray Pearl (KBY)', hex: '#94a3b8', labelZh: '磐石灰 (KBY)', labelEn: 'Boulder Gray Pearl' },
]

export const MAZDA_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'snowflake_white', name: 'Snowflake White Pearl Mica (25D)', hex: '#f8fafc', labelZh: '雪花白珍珠 (25D)', labelEn: 'Snowflake White Pearl' },
  { id: 'jet_black', name: 'Jet Black Mica (41W)', hex: '#0f172a', labelZh: '曜石黑 (41W)', labelEn: 'Jet Black Mica (41W)' },
  { id: 'machine_gray', name: 'Machine Gray Metallic (46G)', hex: '#4b5563', labelZh: '鋼鐵灰 (46G)', labelEn: 'Machine Gray Metallic' },
  { id: 'soul_red', name: 'Soul Red Crystal Metallic (46V)', hex: '#991b1b', labelZh: '魂動紅 (46V)', labelEn: 'Soul Red Crystal (46V)' },
  { id: 'deep_crystal_blue', name: 'Deep Crystal Blue Mica (42M)', hex: '#1e293b', labelZh: '深晶藍 (42M)', labelEn: 'Deep Crystal Blue (42M)' },
  { id: 'polymetal_gray', name: 'Polymetal Gray Metallic (47C)', hex: '#64748b', labelZh: '極境灰 (47C)', labelEn: 'Polymetal Gray (47C)' },
  { id: 'zircon_sand', name: 'Zircon Sand Metallic (48T)', hex: '#927b5e', labelZh: '鋯石砂 (48T)', labelEn: 'Zircon Sand Metallic' },
]

export const JEEP_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'bright_white', name: 'Bright White (PW7)', hex: '#f8fafc', labelZh: '亮白 (PW7)', labelEn: 'Bright White (PW7)' },
  { id: 'black_clearcoat', name: 'Diamond Black Crystal (PXJ)', hex: '#0f172a', labelZh: '鑽石黑 (PXJ)', labelEn: 'Diamond Black Crystal' },
  { id: 'granite_crystal', name: 'Granite Crystal Metallic (PAU)', hex: '#4b5563', labelZh: '花崗岩灰 (PAU)', labelEn: 'Granite Crystal Metallic' },
  { id: 'billet_silver', name: 'Billet Silver Metallic (PSC)', hex: '#cbd5e1', labelZh: '鋼胚銀 (PSC)', labelEn: 'Billet Silver Metallic' },
  { id: 'hydro_blue', name: 'Hydro Blue Pearl-Coat (PBJ)', hex: '#0284c7', labelZh: '水藍珍珠 (PBJ)', labelEn: 'Hydro Blue Pearl' },
  { id: 'firecracker_red', name: 'Firecracker Red (PRC)', hex: '#b91c1c', labelZh: '爆竹紅 (PRC)', labelEn: 'Firecracker Red (PRC)' },
  { id: 'sarge_green', name: 'Sarge Green (PGG)', hex: '#3f4f3e', labelZh: '軍裝綠 (PGG)', labelEn: 'Sarge Green (PGG)' },
  { id: 'high_velocity', name: 'High Velocity Yellow (PJF)', hex: '#eab308', labelZh: '高速黃 (PJF)', labelEn: 'High Velocity Yellow' },
]

export const AUDI_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'ibis_white', name: 'Ibis White (T9)', hex: '#f8fafc', labelZh: '朱鷺白 (T9)', labelEn: 'Ibis White (T9)' },
  { id: 'mythos_black', name: 'Mythos Black Metallic (0E)', hex: '#0f172a', labelZh: '神話黑 (0E)', labelEn: 'Mythos Black Metallic' },
  { id: 'daytona_gray', name: 'Daytona Gray Pearl (6Y)', hex: '#475569', labelZh: '迪通拿灰 (6Y)', labelEn: 'Daytona Gray Pearl' },
  { id: 'florett_silver', name: 'Florett Silver Metallic (L5)', hex: '#cbd5e1', labelZh: '花劍銀 (L5)', labelEn: 'Florett Silver Metallic' },
  { id: 'navarra_blue', name: 'Navarra Blue Metallic (2D)', hex: '#1e3a8a', labelZh: '納瓦拉藍 (2D)', labelEn: 'Navarra Blue Metallic' },
  { id: 'tango_red', name: 'Tango Red Metallic (Y1)', hex: '#991b1b', labelZh: '探戈紅 (Y1)', labelEn: 'Tango Red Metallic' },
  { id: 'nardo_gray', name: 'Nardo Gray (T3)', hex: '#94a3b8', labelZh: '納多灰 (T3)', labelEn: 'Nardo Gray (T3)' },
  { id: 'district_green', name: 'District Green Metallic (M4)', hex: '#3f4f3e', labelZh: '郡區綠 (M4)', labelEn: 'District Green Metallic' },
]

export const LEXUS_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'eminent_white', name: 'Eminent White Pearl (085)', hex: '#f8fafc', labelZh: '卓越白珍珠 (085)', labelEn: 'Eminent White Pearl' },
  { id: 'caviar', name: 'Caviar (223)', hex: '#0f172a', labelZh: '魚子醬黑 (223)', labelEn: 'Caviar (223)' },
  { id: 'cloudburst_gray', name: 'Cloudburst Gray (1L1)', hex: '#4b5563', labelZh: '雲湧灰 (1L1)', labelEn: 'Cloudburst Gray (1L1)' },
  { id: 'iridium', name: 'Iridium (1L2)', hex: '#cbd5e1', labelZh: '銥銀 (1L2)', labelEn: 'Iridium (1L2)' },
  { id: 'grecian_water', name: 'Grecian Water (8Y6)', hex: '#0284c7', labelZh: '希臘水藍 (8Y6)', labelEn: 'Grecian Water (8Y6)' },
  { id: 'matador_red', name: 'Matador Red Mica (3R1)', hex: '#991b1b', labelZh: '鬥牛士紅 (3R1)', labelEn: 'Matador Red Mica' },
  { id: 'nori_green', name: 'Nori Green Pearl (6X4)', hex: '#2d4739', labelZh: '海苔綠 (6X4)', labelEn: 'Nori Green Pearl' },
]

export const VOLVO_COLOR_PRESETS: VehicleColorPreset[] = [
  { id: 'crystal_white', name: 'Crystal White (707)', hex: '#f8fafc', labelZh: '水晶白 (707)', labelEn: 'Crystal White (707)' },
  { id: 'onyx_black', name: 'Onyx Black (717)', hex: '#0f172a', labelZh: '瑪瑙黑 (717)', labelEn: 'Onyx Black (717)' },
  { id: 'platinum_grey', name: 'Platinum Grey (731)', hex: '#4b5563', labelZh: '鉑金灰 (731)', labelEn: 'Platinum Grey (731)' },
  { id: 'silver_dawn', name: 'Silver Dawn (735)', hex: '#cbd5e1', labelZh: '晨曦銀 (735)', labelEn: 'Silver Dawn (735)' },
  { id: 'denim_blue', name: 'Denim Blue (723)', hex: '#1e3a8a', labelZh: '丹寧藍 (723)', labelEn: 'Denim Blue (723)' },
  { id: 'fusion_red', name: 'Fusion Red (725)', hex: '#991b1b', labelZh: '熔岩紅 (725)', labelEn: 'Fusion Red (725)' },
  { id: 'sage_green', name: 'Sage Green (733)', hex: '#475549', labelZh: '鼠尾草綠 (733)', labelEn: 'Sage Green (733)' },
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
 * Prioritizes model-specific OEM palettes before falling back to brand-level presets.
 */
export function getVehicleColorPresets(brandOrLabel?: string | null): VehicleColorPreset[] {
  if (!brandOrLabel) return UNIVERSAL_COLOR_PRESETS
  const s = brandOrLabel.toLowerCase()

  // 1. Model-specific OEM palettes
  if (/\b(m4|f82|f83)\b/.test(s)) {
    return BMW_M4_F82_COLOR_PRESETS
  }
  if (/\b(mustang|gt350|gt500)\b/.test(s)) {
    return FORD_MUSTANG_COLOR_PRESETS
  }
  if (/\b(911|carrera|targa|gt3|gt2)\b/.test(s)) {
    return PORSCHE_911_COLOR_PRESETS
  }
  if (/\brav4\b/.test(s)) {
    return TOYOTA_RAV4_COLOR_PRESETS
  }
  if (/\b(model\s*3|model\s*y)\b/.test(s)) {
    return TESLA_COLOR_PRESETS
  }
  if (/\b(e\s?400|e\s?450|e\s?350)\b.*\bcoupe\b/.test(s)) {
    return MERCEDES_COLOR_PRESETS
  }

  // 2. Brand-level OEM palettes
  if (/\b(mercedes|benz|amg|maybach)\b/.test(s)) return MERCEDES_COLOR_PRESETS
  if (/\btesla\b/.test(s)) return TESLA_COLOR_PRESETS
  if (/\b(lexus)\b/.test(s)) return LEXUS_COLOR_PRESETS
  if (/\b(toyota|scion)\b/.test(s)) return TOYOTA_COLOR_PRESETS
  if (/\b(bmw|mini|rolls-royce)\b/.test(s)) return BMW_COLOR_PRESETS
  if (/\bporsche\b/.test(s)) return PORSCHE_COLOR_PRESETS
  if (/\b(ford|lincoln)\b/.test(s)) return FORD_COLOR_PRESETS
  if (/\b(honda|acura)\b/.test(s)) return HONDA_COLOR_PRESETS
  if (/\b(chevy|chevrolet|gmc|cadillac|corvette|silverado)\b/.test(s)) return CHEVROLET_COLOR_PRESETS
  if (/\b(hyundai|genesis)\b/.test(s)) return HYUNDAI_COLOR_PRESETS
  if (/\bkia\b/.test(s)) return KIA_COLOR_PRESETS
  if (/\bsubaru\b/.test(s)) return SUBARU_COLOR_PRESETS
  if (/\b(nissan|infiniti)\b/.test(s)) return NISSAN_COLOR_PRESETS
  if (/\bmazda\b/.test(s)) return MAZDA_COLOR_PRESETS
  if (/\b(jeep|ram|dodge|chrysler)\b/.test(s)) return JEEP_COLOR_PRESETS
  if (/\b(audi|vw|volkswagen)\b/.test(s)) return AUDI_COLOR_PRESETS
  if (/\bvolvo\b/.test(s)) return VOLVO_COLOR_PRESETS
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

export const VEHICLE_IMAGE_CACHE_VERSION = '20261107v2'

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
 * Resolves color-accurate, transparent cut-out photograph for BMW M4 Coupe and 4 Series.
 */
export function resolveBmwM4ColorPhoto(color?: string | null): string {
  const versionParam = `?v=${VEHICLE_IMAGE_CACHE_VERSION}`
  if (!color || color === '#ffffff' || color === '#fff' || color === '#faf9fb' || color === '#f8fafc') {
    return `/vehicles/bmw_m4_coupe_alpine_white.png${versionParam}`
  }
  const norm = color.toLowerCase().trim()

  const PRESET_FILES: Record<string, string> = {
    '#faf9fb': 'alpine_white',
    '#f8fafc': 'alpine_white',
    '#ffffff': 'alpine_white',
    '#f0f0ee': 'mineral_white',
    '#121417': 'black_sapphire',
    '#0f172a': 'black_sapphire',
    '#111827': 'black_sapphire',
    '#1a1f2c': 'black_sapphire',
    '#1e293b': 'black_sapphire',
    '#484b50': 'mineral_grey',
    '#475569': 'mineral_grey',
    '#4b5563': 'mineral_grey',
    '#374151': 'mineral_grey',
    '#525a65': 'mineral_grey',
    '#b8c3cc': 'silverstone',
    '#94a3b8': 'silverstone',
    '#a8b0b8': 'silverstone',
    '#cbd5e1': 'silverstone',
    '#5c9dc0': 'yas_marina_blue',
    '#38bdf8': 'yas_marina_blue',
    '#1c3b72': 'san_marino_blue',
    '#1e3a8a': 'san_marino_blue',
    '#1d4ed8': 'san_marino_blue',
    '#1b2a47': 'san_marino_blue',
    '#d2b134': 'austin_yellow',
    '#eab308': 'austin_yellow',
    '#a8322d': 'sakhir_orange',
    '#991b1b': 'sakhir_orange',
    '#dc2626': 'sakhir_orange',
    '#b91c1c': 'sakhir_orange',
    '#ea580c': 'sakhir_orange',
  }

  if (PRESET_FILES[norm]) {
    return `/vehicles/bmw_m4_coupe_${PRESET_FILES[norm]}.png${versionParam}`
  }

  const rgb = parseHexRgb(norm)
  if (!rgb) {
    return `/vehicles/bmw_m4_coupe_alpine_white.png${versionParam}`
  }

  let bestPreset = 'black_sapphire'
  let minDistance = Infinity
  for (const preset of BMW_M4_F82_COLOR_PRESETS) {
    const pRgb = parseHexRgb(preset.hex)
    if (!pRgb) continue
    const dist = (rgb[0] - pRgb[0]) ** 2 + (rgb[1] - pRgb[1]) ** 2 + (rgb[2] - pRgb[2]) ** 2
    if (dist < minDistance) {
      minDistance = dist
      bestPreset = preset.id
    }
  }
  return `/vehicles/bmw_m4_coupe_${bestPreset}.png${versionParam}`
}

/**
 * Resolves color-accurate, transparent cut-out photograph for Toyota RAV4 and Crossover SUVs.
 */
export function resolveToyotaColorPhoto(color?: string | null): string {
  const versionParam = `?v=${VEHICLE_IMAGE_CACHE_VERSION}`
  if (!color || color === '#ffffff' || color === '#fff' || color === '#f8fafc') {
    return `/vehicles/toyota_rav4_wind_chill_pearl.png${versionParam}`
  }
  const norm = color.toLowerCase().trim()

  const PRESET_FILES: Record<string, string> = {
    '#f8fafc': 'wind_chill_pearl',
    '#ffffff': 'wind_chill_pearl',
    '#111827': 'midnight_black',
    '#0f172a': 'midnight_black',
    '#1a1f2c': 'midnight_black',
    '#1e293b': 'midnight_black',
    '#4b5563': 'magnetic_gray',
    '#374151': 'magnetic_gray',
    '#525a65': 'magnetic_gray',
    '#475569': 'magnetic_gray',
    '#cbd5e1': 'celestial_silver',
    '#94a3b8': 'celestial_silver',
    '#a8b0b8': 'celestial_silver',
    '#1d4ed8': 'blueprint',
    '#1e3a8a': 'blueprint',
    '#1b2a47': 'blueprint',
    '#991b1b': 'ruby_flare',
    '#7a1c27': 'ruby_flare',
    '#dc2626': 'ruby_flare',
    '#b91c1c': 'ruby_flare',
    '#3f4f3e': 'army_green',
    '#166534': 'army_green',
    '#15803d': 'army_green',
  }

  if (PRESET_FILES[norm]) {
    return `/vehicles/toyota_rav4_${PRESET_FILES[norm]}.png${versionParam}`
  }

  const rgb = parseHexRgb(norm)
  if (!rgb) {
    return `/vehicles/toyota_rav4_wind_chill_pearl.png${versionParam}`
  }

  let bestPreset = 'wind_chill_pearl'
  let minDistance = Infinity
  for (const preset of TOYOTA_COLOR_PRESETS) {
    const pRgb = parseHexRgb(preset.hex)
    if (!pRgb) continue
    const dist = (rgb[0] - pRgb[0]) ** 2 + (rgb[1] - pRgb[1]) ** 2 + (rgb[2] - pRgb[2]) ** 2
    if (dist < minDistance) {
      minDistance = dist
      bestPreset = preset.id
    }
  }
  return `/vehicles/toyota_rav4_${bestPreset}.png${versionParam}`
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
  if (
    /\b(bmw\s+m4|m4\s+coupe|m4|430i|m440i)\b/i.test(s) ||
    (/\bbmw\b/i.test(s) && /\b(m4|4\s*series|3\s*series|330i|m340i|m3)\b/i.test(s))
  ) {
    return resolveBmwM4ColorPhoto(color)
  }
  if (
    /\b(rav4|cr-?v|rogue|tucson|forester|crosstrek|sportage|cx-?5|equinox|highlander|rx\s?350|nx\s?350)\b/i.test(s) ||
    (/\b(toyota|honda|nissan|hyundai|subaru|kia|mazda)\b/i.test(s) && /\b(suv|crossover)\b/i.test(s))
  ) {
    return resolveToyotaColorPhoto(color)
  }
  return null
}
