# 車型自動油耗基準

已接入 FuelEconomy.gov 官方 EPA／DOE 車型服務。使用者只需選擇年份、品牌、車型與配置，搜尋時傳入 `vehicle_id`；不用填 MPG 或記錄加油。

## 智慧文字選車與油種自動帶入

也可直接使用 `POST /v1/vehicles/vin` 解碼 VIN，再對應 EPA 配置；唯一匹配時自動取得 MPG 與油種，仍有差異才追問。[VIN API 與驗證](vin-selection.md)

州別＋車牌入口為 `POST /v1/vehicles/plate`；接口已完成，實際查詢需配置可用服務金鑰。AutoZone 網站調查目前受 Access Blocked 阻擋，沒有宣稱已串接。[車牌來源與啟用狀態](plate-selection.md)

`POST /v1/vehicles/resolve` 支援 `{"text":"2018 benz e400"}`，依官方目錄而非 LLM 猜測選車；支援 benz／Mercedes-Benz／mercedes benz／mb 與部分品牌別名。這是 GasWise 的互動選車實作，AutoZone 網站為互動參考，沒有接入或嵌入 AutoZone 私有 API。

支援大小寫、空格／連字號／底線、全形字元與品牌別名；拼字接近時提供需確認的候選，不把模糊分數當成車型確定。型號數字不做任意替換，E499 不會自動變成 E400。部分型號可提供候選；明確的 E400 不混入 E4000。

回應 `status:needs_input` 提供 `question`、`answer_field`、`choices[{value,label}]`、`selection` 與 `missing_fields`。前端將回傳 `selection` 作為下一次請求，加入指定欄位答案即可；不必叫使用者重打一整句。基本欄位為 `year`、`make`、`model`，配置欄位仍有 `body_style`、`drivetrain`、`catalog_model`、`option_vehicle_id`。範例：

```json
{"text":"2018 benz e400","body_style":"coupe","drivetrain":"4matic"}
```

可用 `{}` 或 `{"text":""}` 開始，依序詢問年份、車廠、型號；每次只問下一個缺少／有歧義的欄位。已有文字中可辨识的資訊會在取得必要的年份目錄後沿用。缺年份時不做全品牌／跨年份查詢；知道年份後選單查詢使用既有公開 metadata 快取，候選選單最多展示 50 項，可直接輸入型號。

`2018 mercedes benz e400` 會先問有差異的車身，選 Coupe 後才問標準／4MATIC；如果文字已包含 `coupe 4matic` 就直接定位配置。多個引擎／變速箱選項會繼續詢問 `option_vehicle_id`，不選第一筆。不存在的配置回應 `no_match`，並指出要修正的 `model` 欄位。車身目錄未明示者標成「其他／目錄未標示」，不推斷它一定是 Sedan。

逐步範例：`{}` → `answer_field:year` → 傳回 selection 加 `year:2018` → `answer_field:make` → 加 `make:Mercedes-Benz` → `answer_field:model` → 加 `model:E400 Coupe` → `answer_field:drivetrain` → 加 `drivetrain:4matic` → resolved。

成功回應 `status:resolved`、`vehicle`、`fuel_recommendation`。實際官方驗證：2018 E400 Coupe 標準後驅 ID `38902`，4MATIC Coupe ID `38903`，均為 Premium Gasoline、綜合 22 MPG。

將回傳 `vehicle.id` 送到搜尋 API；省略 `fuel_type` 時會在取得油價前，自動使用車型的 regular／midgrade／premium／diesel，無須手選。車型記錄也帶 `fuel_recommendation` 與 EPA 燃料描述。明確提供 `fuel_type` 仍可覆寫；汽油／柴油不相容會拒絕。沒有車型時省略油種保留原 API 的 premium 預設。

EPA 的燃料描述是目錄基準，不是原廠最低辛烷值保證；`octane_aki:null`、`manufacturer_requirement_verified:false` 明示尚無原廠依據。沒有憑品牌或 Premium 標籤推斷 91／93 AKI，也沒有把歐洲 RON 誤當美國 AKI。已有 `required_octane` 的明確請求仍維持站點驗證規則。

資料契約來源：[官方 Web Services](https://www.fueleconomy.gov/feg/ws/index.shtml)。

## 前端選車流程

以下 GET 使用與其他 GasWise API 相同的 Bearer token：

1. `/v1/vehicles/years`
2. `/v1/vehicles/makes?year=2012`
3. `/v1/vehicles/models?year=2012&make=Honda`
4. `/v1/vehicles/options?year=2012&make=Honda&model=Fit`
5. `/v1/vehicles/31819`

選單回傳 `items[{text,value}]`；最後一層的 `value` 是 EPA 車型 ID。必須選到配置，不能把同名車型的不同變速箱／引擎／驅動方式合併。前端儲存 ID 即可供後續搜尋使用；目前後端沒有使用者帳戶或個人車庫儲存。

官方選單可能含 EV、PHEV、FFV／替代燃料配置；選定 ID 後必須查詢詳情確認是否支援，不能宣稱選單已排除全部不支援車型。目前僅支援單燃料汽油、柴油、非插電式汽油 HEV；EV／PHEV、雙燃料與其他燃料明確回報 `vehicle_powertrain_not_supported`，不使用 MPGe。

## 搜尋與重新排名

```json
{
  "origin": {"lat": 34.0522, "lng": -118.2437},
  "vehicle_id": 31819,
  "fuel_type": "regular",
  "gallons": "10"
}
```

傳給 `POST /v1/recommendations`，或加 `calculate_routes:true` 傳給 `/v1/smart/search`。原有油價、付款條件、會員與路線限制仍適用。車型紀錄查詢／燃料相容性驗證先於油價及路線查詢；查詢失敗不默默改成 20 MPG。車型燃油描述不驗證數字辛烷值；省略油種時自動帶入，明確選擇時保留覆寫。汽油車選柴油或柴油車選汽油會明確失敗。

耗油基準優先序：

1. 明確提供完整週期紀錄（既有進階選項）。
2. 明確提供 `mpg` 覆寫。
3. 所選車型 EPA **綜合 MPG**。
4. 無車型也無其他資料時，保留舊 API 的 20 MPG，回傳明確警告。

`mpg` 現在可省略或為 `null`，而非默認寫入 20；這讓車型基準能自然生效。`/v1/smart/rerank` 的 `options.mpg:null` 可清除先前覆寫，恢復 EPA 基準；`fuel_cycles:[]` 清除個人週期校準。省略選項則保留既有選項。重新排名不允許更换 `vehicle_id`；要換車時建立新搜尋。

回應包含 `vehicle` 的車型、引擎、變速箱、驅動方式、三種 MPG、來源與取得時間。每個排名包含 `fuel_model.vehicle`、`mpg_used` 與 `fuel_consumption_basis:epa_combined_estimate`（若使用 EPA）。Smart snapshot 包含車型紀錄並納入簽章；重新排名僅使用簽章內資料，零車型／油價／路線上游呼叫。

## 快取、成本與精度邊界

- 官方車型服務不使用 Google key；沒有新增 Google 付費呼叫、輪詢或自動重試。
- 選單／車型為低頻變動的公開中繼資料，使用程序內 24 小時、最多 128 筆成功紀錄快取；重啟清空，失敗不快取，過期不以舊紀錄遮蔽失敗。這不是油價／交通快取。
- Smart 的 `vehicle_catalog_lookup` 是邏輯車型查詢數，快取命中可無 HTTP；重新排名為 0。選單端點查詢不包含在搜尋計數內。
- 市區／高速 MPG 回傳作為參考，沒有假設路段比例；Maps 總時間只影響時間成本。
- EPA MPG 是標準化車型基準，並非該使用者或該路線實測。没有虛構坡度、冷氣、怠速或天氣修正。
- RouteE 尚未啟用；需要另行取得並驗證逐段距離／速度／坡度及適用車型模型。現階段完成的是無需使用者油耗紀錄的自動車型基準。

## 驗證

2026-10-10：直接官方 HTTP 驗證 2012 Honda 的車型選單（17 項）、Fit 配置（3 項）與 `31819` 詳情：汽油、1.5 L、Automatic (S5)、FWD，市區 27／高速 33／綜合 30 MPG。這是資料取得驗證，沒有實車耗油精度驗證。

模擬測試涵蓋車型身份、單／多項選單、參數編碼、快取與快取隔離、失敗不快取、非法 MPG、EV／PHEV／替代燃料排除、燃料不匹配、API 自動 MPG、簽章防竄改、覆寫／恢復基準與零上游重新排名。
