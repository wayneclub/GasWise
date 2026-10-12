# GasWise 前端規劃（MVP）

> 狀態（2026-10-11）：F0–F3 已完成於 `frontend/`，見 [frontend/README.md](../frontend/README.md)。實作差異：不使用 shadcn/ui 與 TanStack Query（手寫元件與一個 session hook 已足夠）；採暖米白、僅淺色主題；地址轉座標端點仍未提供，開發模式以 DTLA 作為定位失敗的備援。

依據產品計劃書，核對 `backend/` 現況（2026-10-11）後的前端設計與開發順序。

## 1. 計劃書 vs 後端現況

| 計劃書項目 | 後端現況 | 前端要做的事 |
| --- | --- | --- |
| Round Trip / On My Way 兩種繞路模型 | ✅ `trip_mode=round_trip/on_route`，on-route 用 `D_via − D_original` | MVP 只做 round trip；Trip 模式放 P1 |
| 繞路「時間」而非只有距離 | ✅ `extra_travel_minutes`、`detour_miles` | 卡片顯示「4 min extra」 |
| Break-even gallons | ✅ `RankedStation.break_even`（fuel-only / 含時間兩種門檻，基準站 = 最快站） | 轉成一句話：「加超過 3.5 gal 這趟才划算（對比 Shell）」 |
| Best Overall / Lowest Cost / Quickest | ✅ `ranking.recommendations` 四張卡：`best_value`、`cheapest_overall`、`fastest_stop`、`on_my_route` | 首頁直接用，不必自己排序 |
| `Score = C + λT` 與 Save Money / Balanced / Save Time | ⚠️ λ = `time_value_per_hour`，**預設 0** | 前端 preset：Money=0、Balanced=15、Time=30 (USD/h)，或由後端提供 `preference` enum |
| 推薦可信度 | ⚠️ 有 `freshness`、`price_comparison.quality`、`decision.status`，**但沒有覆蓋率摘要** | 前端先自行推導（見 §4），建議後端補 `coverage` 欄位 |
| 「Best among verified prices」降級文案 | ❌ 後端沒有 | 前端依可信度切換標籤 |
| 硬性篩選（會員、付款方式、Premium、價格過期） | ✅ `memberships`、`payment_type`、`required_octane`、`max_price_age_minutes` | Settings 中設定 |
| 硬性篩選：營業中 | ✅ `opening_policy`（預設排除已打烊；未知營業時間保留並警告）、`station.open_now`、`details.opening_status` | 卡片顯示「Closes 10 PM」；未知營業時間標示「Hours unknown」 |
| 成本說明（Why Chevron?） | ✅ `purchase_cost`、`detour_fuel_cost`、`actual_fuel_cost`、`break_even.fuel_savings_at_requested_gallons` | 「Why?」展開區直接渲染 |
| 兩階段排序省 API | ✅ `/smart/search`（取一次價）→ `/smart/routes`（≤10 條路線）→ `/smart/rerank`（**0 次上游呼叫**） | 改加油量／偏好只打 rerank |
| 車型 MPG | ✅ `/v1/vehicles/resolve`（例如輸入 "2018 benz e400"）、VIN、車牌、EPA MPG | Onboarding 用文字解析 + 選項 chips |
| 一鍵導航 | — | 前端產生 Google Maps / Apple Maps / Waze deep link |
| PostgreSQL + PostGIS | 刻意不用（無狀態，Google 內容不落地） | MVP 同意。偏好存 localStorage；**snapshot 不可存** |
| Data Feasibility（Go/No-Go） | ⚠️ 只有 DTLA 一次 smoke：38 筆有座標報價中，**33 筆付款條件未知，只有 3 筆通過預設篩選** | 見 §6。這仍然是最大風險 |

不在計劃書範圍內的後端模組：`parts/`（O'Reilly / AutoZone / MANN 零件相容性）、車輛規格爬取。前端不接這些，建議之後評估是否從 GasWise 拆出去。

## 2. 開始做前端前，必須先處理的後端缺口

1. **認證**：目前是靜態 service token，README 明確寫不能放進瀏覽器 bundle。
   - 本機：Vite dev proxy 代為注入 `Authorization`（token 只放在 `frontend/.env.local`，不能用 `VITE_` 前綴）。
   - 部署：需要一個薄 BFF / gateway 注入 token 並做 rate limit，或改成 per-user session。後端沒有 CORS，同源 proxy 正好不需要。
2. **地理編碼**：沒有地址 → 座標的端點。定位被拒時要手動輸入地點，Trip 模式也要輸入目的地，這兩個都會卡住。
3. **覆蓋率摘要**（建議）：`ranking.coverage = {inventory, priced, eligible, routed}`。

## 3. 技術選型

| 層 | 選擇 | 理由 |
| --- | --- | --- |
| Build | Vite + React 19 + TypeScript | 依計劃書 |
| UI | Tailwind CSS v4 + shadcn/ui | 依計劃書；元件可控 |
| 視覺規範 | taste-skill（`design-taste-frontend`） | 見 §7 |
| Server state | TanStack Query | 需要處理去重、取消、錯誤重試政策 |
| 型別 | `openapi-typescript` 從 `contracts/openapi.json` 產生 | 合約即真相，後端改了 CI 會壞 |
| Client state | localStorage 包一層小 hook（車輛、加油量、偏好） | 不需要 Redux / Zustand |
| 地圖 | **MVP 不做** | Google 來源資料顯示在非 Google 地圖上有授權疑慮；先用 deep link |

金額一律是 Decimal 字串：**只格式化顯示，不在前端用 float 重算**。需要重算時一律打 rerank。

## 4. 推薦可信度規則（前端推導，v1）

```
High    decision.status == "robust"
        且 winner.freshness ∈ {fresh, aging}
        且 price_comparison.quality != "disputed"
Medium  decision.status ∈ {"uncertain", "single_source"}，或 winner.freshness == "aging"
Low     winner.freshness ∈ {stale, unknown}，或 quality == "disputed"，或可比較站數 < 3
None    decision.status == "no_eligible_stations"
```

- High → 標籤 `🏆 Best Overall`
- Medium / Low → `Best among verified prices`，並顯示原因（例如 "Price updated 3 days ago"、"Only 3 of 20 nearby stations have usable prices"）
- 站數：`ranking.results.length + ranking.excluded_count` 對比 `snapshot.inventory.length`

## 5. 資訊架構與畫面

```
/            Decide（首頁）
/setup       Onboarding（第一次開啟才會進來）
/settings    車輛・加油量・付款・會員・偏好
/trip        On My Way（P1）
```

### 5.1 Onboarding（約 30 秒）
1. 車輛：文字輸入 → `/vehicles/resolve` → 用 chips 回答剩下的歧義（例如 RWD / 4MATIC）→ 得到 `vehicle_id`、油品等級、EPA MPG。可「跳過」，改選油品並填 MPG。
2. 一般加多少：stepper，預設 10 gal。
3. 付款：Credit / Cash；Costco 會員開關。
4. 偏好：Save Money / Balanced / Save Time。

### 5.2 Decide（首頁）— Progressive disclosure
開啟後：讀取偏好 → 要求定位 → `POST /v1/smart/search`（`calculate_routes: true, route_limit: 5`）。

```
┌───────────────────────────────────────┐
│ Premium 91 · 10 gal · E400      [編輯]│  ← 情境列（點開即改，打 rerank）
├───────────────────────────────────────┤
│ 🏆 BEST OVERALL            ● High     │
│ Chevron                                │
│ $5.79/gal   Save $3.20   +4 min       │
│ [ Navigate ]              Why? ▾      │  ← 第一層
├───────────────────────────────────────┤
│ 💰 Lowest cost  Costco  $5.45  +17 min │  ← 第二層
│ ⚡ Quickest     Shell   $5.99  +1 min  │
├───────────────────────────────────────┤
│ Prices updated 12 min ago · 3 sources │  ← 第三層（往下滑）
│ All stations ▸  How we calculate ▸     │
└───────────────────────────────────────┘
```

- 三張卡若是同一站，就合併顯示 badge（例如「Best & Cheapest」），不重複列出。
- **Why? 展開區**：`10 gal × $5.79 / Extra driving fuel / Estimated total / vs Quickest (Shell) / Savings`，再加 break-even 一句話與各來源報價時間。
- **改加油量或偏好** → `/smart/rerank`，0 次上游呼叫，數字即時變動。
- **不要**自動刷新、不要背景輪詢、不要因 GPS 抖動重新搜尋；只放一個明確的「Refresh prices」。
- 搜尋期間按鈕要 disable（後端雖然會合併相同請求，但每次 stage-1 都消耗配額）。

### 5.3 狀態設計（和主畫面一樣重要）

| 情境 | 判斷 | UI |
| --- | --- | --- |
| 取價中（3–10 秒） | pending | 骨架卡片 + 分段文案（Finding stations → Checking prices → Measuring detours） |
| 定位被拒 | Geolocation error | 手動輸入地點（**需要地理編碼端點**） |
| 沒有合格站 | `no_eligible_stations` | 告訴使用者原因，並提供一鍵放寬：包含付款條件未知的價格 / 放寬價格時效 / 擴大半徑 |
| 可信度低 | §4 | 降級標籤 + 原因 |
| Snapshot 過期（10 分鐘） | rerank 回 409 | 自動提示「Prices expired · Refresh」 |
| 忙碌 | 429 + `Retry-After` | 倒數後才能重試 |
| 來源失敗 | 502 / 504、`source_statuses` | 部分來源失敗時仍顯示結果，並標示哪個來源缺失 |
| 歸屬標示 | `station.attribution` | 依 Google 政策顯示來源歸屬 |

## 6. Go/No-Go：資料可行性先行

DTLA 的 smoke 結果顯示，在預設的「credit、排除付款條件未知」下，只有 3 / 38 筆報價合格。這代表首頁很可能經常落在 Low / None 狀態。開始打磨 UI 之前：

1. 寫一支 `scripts/smoke/feasibility.py`，對 DTLA、Rowland Heights、Irvine 各跑 Regular 和 Premium，輸出：站點覆蓋、有價比例、24h 內更新比例、付款條件已知比例、合格比例。
2. 依結果決定預設值：`allow_unknown_payment` 預設要不要開，開的話首頁要怎麼標示。
3. 用你自己的 E400 實地加油紀錄做比對（現場誤差 ≤ $0.10/gal）。

前端可以和 1 並行開發，因為後端 `GASWISE_MODE=demo` 有合成資料、不耗配額。

## 7. taste-skill 用法

```bash
npx skills add https://github.com/Leonxlnx/taste-skill --skill "design-taste-frontend"
```

這是工具型產品，要求的是「一眼看懂、單手操作」，不是行銷頁。建議 dial：

- **VARIANCE 3**：版面穩定，不要實驗性排版
- **MOTION 2**：只做 hover / 數字變化過渡，**不要 GSAP 或捲動動畫**（v2 內附的 GSAP 骨架略過）
- **DENSITY 6**：數字資訊密度要夠，但第一層只放一個答案

視覺方向可參考 `minimalist-skill`。補充專案規則：價格用 tabular numerals；金額永遠搭配單位與時間；顏色不單獨承載意義（可信度同時用文字表示）；手機寬度優先（375px）。

## 8. 開發里程碑

| 階段 | 內容 | 完成條件 |
| --- | --- | --- |
| F0 | 建立 `frontend/` 骨架、OpenAPI 型別產生、Vite proxy、design tokens、安裝 taste-skill | `npm run dev` 透過 proxy 打 demo 後端成功 |
| F1 | Decide 首頁：search → 三張卡 → Navigate deep link | demo 模式下可以完整走一次 |
| F2 | Onboarding + Settings（車輛解析、偏好 → rerank） | 改加油量時數字更新，network 只出現 rerank |
| F3 | Why? 成本說明、break-even 文案、§4 可信度、§5.3 全部狀態 | 每個狀態都有 fixture / Storybook 或測試 |
| F4 | 實地測試：DTLA / Rowland Heights / Irvine | 依 §6 指標回報 |
| P1 | Trip（on-route）、地圖 | 需要地理編碼 |

### 前端目錄

```
frontend/
├── src/
│   ├── api/            # 產生的 schema.d.ts、fetch client、錯誤對應
│   ├── features/
│   │   ├── decide/     # 首頁、推薦卡、Why 展開
│   │   ├── setup/      # onboarding、車輛解析
│   │   └── settings/
│   ├── lib/            # money 格式化、confidence、deeplink、geolocation
│   ├── components/ui/  # shadcn
│   └── prefs.ts        # localStorage 偏好（不存 snapshot）
└── vite.config.ts      # /api → 127.0.0.1:8000 proxy，注入 token
```

## 9. 成功指標的前端埋點（之後再接）

Time to Recommendation（開啟 → 首卡出現）、Navigation Conversion（點 Navigate / 看到推薦）、Valid Recommendation Rate（High+Medium / 全部查詢）。MVP 只先記 console / local，不接第三方分析。
