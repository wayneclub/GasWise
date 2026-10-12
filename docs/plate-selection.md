# 州別＋車牌查詢車型

後端接口與 Vehicle Databases 適配器已完成，但未啟用、未做該供應商的實測。**AutoZone 已完成一組使用者授權的真實車牌瀏覽器驗證**，得到正確年份、車廠、型號、引擎與 VIN；已接入 GasWise，NHTSA 已確認 Coupe；EPA 對應尚未成功。Vehicle Databases 金鑰不是繼續調查 AutoZone 的必要條件。

## API 與流程

`POST /v1/vehicles/plate`，使用既有 GasWise Bearer token：

```json
{
  "state": "CA",
  "plate": "你的車牌"
}
```

州別必填，支援 50 州與 DC；大小寫自動統一。車牌目前支援 ASCII 字母／數字，移除空格／連字號，1–10 碼；特殊符號車牌可改用 VIN。沒有用 GPS 猜車牌州別。

1. 車牌服務依州別與車牌查詢 VIN、基本年份／車廠／型號。
2. 核對回應的州別與車牌；缺 VIN、不合格式或身份不符就拒絕。
3. 使用既有 NHTSA 解碼；已知年份也必須一致。車廠不符會拒絕，型號名稱不一致會要求確認。
4. 只有唯一且與 VIN 已知資訊一致的 EPA 配置，才帶入 MPG 與建議油種；其他狀態沿用 VIN 的 partial／needs_input／no_match／unsupported。

回應 `resolution` 為既有 VIN 選車結果，成功可取得 `resolution.vehicle.id` 與 `fuel_recommendation`。將 ID 傳給 recommendations／smart search，省略 MPG／油種即可。候選仍不唯一時可再傳相同州別／車牌與 `vehicle_id` 確認；每次新的提交都可能再產生一次車牌供應商查詢。

車牌資料可能落後轉牌／換車；唯一 EPA 候選不是原廠完整配置或現時註冊身份保證。最低辛烷值仍遵守原有原廠證據限制，沒有由車牌猜測 91／93 AKI。

## 目前可配置的來源

使用 [Vehicle Databases 官方 Plate Decode API](https://www.vehicledatabases.com/docs/api-documentation/plate-decode/)：

```text
GET https://api.vehicledatabases.com/plate-decode/{plate}/{state}
x-authkey: <服務金鑰>
```

僅有接口文件不表示已取得服務授權或可用額度；實際費用／覆蓋率以帳戶服務為準。啟用需在後端私有設定加入：

```dotenv
GASWISE_PLATE_LOOKUP_ENABLED=true
GASWISE_VEHICLE_DATABASES_API_KEY=<服務金鑰>
GASWISE_API_TOKEN=<GasWise API存取金鑰>
```

預設未啟用，`/v1/capabilities` 回傳 `plate_lookup_enabled:false`；車牌端點回傳 503 `plate_provider_not_configured`，在任何上游呼叫之前停止。API 金鑰不可放在前端或聊天中；沒有自行申請帳戶、購買服務或偷偷改用付費來源。

一次 plate 請求最多一次供應商操作，不輪詢、不重試、不自動 fallback。提供 `plate_lookup`、`nhtsa_decode`、`epa_lookup` 邏輯計數；EPA metadata 可命中既有快取。沒有新增 Google 呼叫。

GasWise 使用 POST body 接收車牌；供應商官方契約仍是帶車牌的 GET URL，不能宣稱上游 URL 沒有車牌。服務金鑰只放 header。成功回應只保留車牌末兩碼（兩碼以下全遮罩）與 VIN 末四碼，不建立車牌查詢歷史或額外 body log；外部代理另行啟用日誌的行為不在此承諾內。

## AutoZone 調查與實際驗證狀態

2026-10-10：使用 reverse-engineer-anything 技能的證據區分流程，對用戶指定 AutoZone 公開網站作有限觀察：

- 匿名 HTTP GET 首頁回傳 **403**，850 bytes，頁面指向 captcha-delivery 的裝置檢查。
- Codex 正常 in-app browser 開啟同網站，accessibility 內容顯示 **DataDome Device Check／AutoZone - Access Blocked**。
- 沒有繞過檢查、枚舉車牌、取得私有金鑰或猜測 AutoZone 車牌接口；尚未觀察到實際車牌請求／回應。
- 這些是 HTTP／瀏覽器觀察，沒有取得可用的 REA runtime capture 或可重播的 AutoZone 成功請求。不能寫成 AutoZone 適配器已完成。

合成車牌及模擬 Vehicle Databases 測試涵蓋：格式／州別、官方端點與 header、身份核對、車牌→VIN→EPA→MPG／油種、車廠／型號衝突、無紀錄／401／429／500 不重試、未配置零上游呼叫、認證設定、成功 API 遮罩輸出。該適配器沒有進行真實車牌資料的 live smoke。

### 2026-10-10 後續：AutoZone 真實瀏覽器驗證成功

證據方法：正常 Brave 瀏覽器表單操作，操作前啟用 CDP Network capture，核對 XHR 回應、UI 結果及已載入 JavaScript。REA MCP 工具未出現在本次 session；使用 REA 的證據區分方法，不宣稱取得 REA Evidence ID。

- AZ-01（觀察）：Brave 成功進入首頁，Add Vehicle → License Plate 可選州別、輸入車牌，無需登入。先前匿名 HTTP／in-app browser 阻擋不代表正常瀏覽器無法使用。
- AZ-02（觀察）：州別資料 `GET /ecomm/b2c/v1/utility/states` 回傳 200。
- AZ-03（觀察）：合成字串 `TEST123`、CA 觸發下列 GET，XHR 回傳 404，UI 顯示查無車牌；不是身份驗證成功案例。
- AZ-04（觀察）：使用者提供並授權查詢的 CA 車牌（文件只留末兩碼 **42）觸發相同端點，XHR `9661.744` 回傳 **200**，JSON 陣列只有一筆：`vehicleName=2018 Mercedes-Benz E400`、`makeName=Mercedes-Benz`、`modelName=E400`；`acesVehicleAttributes.year=2018`、`subModelName=Base`、`engineName=6 Cylinders 3.0L Turbo`。回應含 VIN，完整 VIN 不保存於文件／fixture。
- AZ-05（觀察）：首頁更新為 `My Vehicle 2018 Mercedes-Benz E400`；選車視窗顯示相同車型、Base 及 6 Cylinders 3.0L Turbo。

已觀察端點（真實車牌不寫入 URL 範例）：

```text
GET https://external-api.autozone.com/sls/b2c/product-discovery-product-data/v1/vehicles/search-by-vin-or-license-plate
query: licensePlate=<plate>&state=<state>&callingClient=DIY-DESKTOP&country=USA
```

AZ-06（靜態證據）：實際載入的 `/_next/static/chunks/72157-8cb76bf8c86910ea.js` 中，`licensePlateV2` 查詢函式檢查車牌及州別，向 v1 或受 feature flag 控制的 v2 端點送出上述參數，將每筆回應的 `vin`、`vehicleName`、`modelName`、`acesVehicleAttributes` 映射成選車資料。此次網路證據證實走 v1；v2 與其他舊版端點只有靜態線索，未實測。

精確度邊界：年份／廠牌／E400 與使用者已知資訊一致；引擎文字及 Base 是供應商直接回傳值。Coupe 沒有直接文字證據；`bodyNumDoorsId=7`、`driveTypeId=7`、`transmissionBaseId=105_5_19_5` 等為未解碼的 ACES ID，不能憑 ID 猜車身、驅動或變速箱。成功瀏覽器操作不證明無瀏覽器的後端重播可用，也不证明已唯一對應 EPA MPG／油種。

### 2026-10-10 後續：獨立 Python HTTPS 查詢成功

AZ-07（runtime 觀察）：在 backend 以全新 `httpx.Client` 發送一次使用者授權車牌查詢，未登入、不讀取瀏覽器 cookie/session、不帶 Authorization／Cookie／API key。HTTP **200**，回傳一筆 `2018 Mercedes-Benz E400`、`6 Cylinders 3.0L Turbo`、`Base`，且含 VIN；完整車牌／VIN 未保存於文件或 fixture。

成功請求使用普通公開標頭：`Accept: application/json, text/plain, */*`、`Referer: https://www.autozone.com/`、`Origin: https://www.autozone.com`、`X-Requested-By: MF`、`sales-channel: AZRMFWEB`，以及與已觀察瀏覽器相同的 User-Agent。這些值不是登入憑證。尚未逐一刪除標頭測試，不宣稱每一個都是必要條件。

較早的最小 httpx 預設標頭請求（`trust_env=False`）等待回應 30 秒後 ReadTimeout，並非 401／403。成功請求沿用一般 httpx 環境設定且加入上述標頭，因此不能單憑這兩次比較斷定超時原因。已證實本機可直接用 Python HTTPS、無登入憑證查詢此案例；未保證其他部署 IP 或長期可用性。

尚待工作：新增 AutoZone 適配器與來源選擇，核對 VIN／ACES 的 Coupe 配置，再驗證 VIN → EPA 對應。保持現有車牌功能預設關閉，直到該整合完成。此次 plate/VIN/vehicle selection 回歸測試為 66 passed；AZ-07 是獨立 AutoZone HTTP live smoke，尚未經 GasWise API。


### GasWise AutoZone 適配器已接入

設定 `GASWISE_PLATE_LOOKUP_SOURCE=autozone`、`GASWISE_PLATE_LOOKUP_ENABLED=true`，保留既有 `GASWISE_API_TOKEN`。不需要 Vehicle Databases 金鑰。預設程式來源仍為 vehicle_databases，以維持舊設定相容；本機 .env 及 .env.example 選用 autozone。本機 .env 已啟用，執行中的服務需重新啟動才會讀取新設定。

`POST /v1/vehicles/plate` 契約不變；回應 source 為 autozone，新增 source_make／source_model／source_year 保留供應商命名。AutoZone 不回傳車牌／州別 echo，不能宣稱完成 Vehicle Databases 那種 echo 身份核對，回應 warning 明示此限制。拒絕多筆結果、不完整 VIN／年份／品牌／型號；404／空陣列為無紀錄，401／403／429／上游錯誤均不重試、不 fallback。請求移除共享 client 的 Cookie／Authorization／API key，也不跟隨 redirect。

AZ-08（GasWise API live smoke）：以 create_app → FastAPI TestClient → 真實 AutoZone／NHTSA／EPA HTTP 呼叫，API 回傳 200。NHTSA 得到 2018 MERCEDES-BENZ E-Class，body_class=Coupe、3.00L、6 cylinders、Automatic、error_codes=[0]。車牌來源型號 E400；既有 VIN resolver 無法可靠對應 EPA model，status=no_match、vehicle=null，未套用 MPG 或油種。邏輯計數 plate_lookup=1、nhtsa_decode=1、epa_lookup=2。這是 API handler／真實上游驗證，未宣稱已驗證正在執行的部署服務。


### 免費來源配對修正與汽油類別分開回報

NHTSA 的 E-Class 配上 trim `E 400`，現在可以在原有型號搜尋無結果時，以完整 trim 比對 EPA 型號（保留數字邊界，E400 不匹配 E4000），再核對車身、引擎、燃料、變速箱及已知驅動資訊。不新增付費供應商、不擴大無界查詢。

AZ-09（真實 GasWise API）：回傳 200，status=needs_input、fuel_status=epa_catalog、mpg_status=needs_confirmation；候選為 38903 E400 4matic Coupe 與 38902 E400 Coupe。兩者均為 Premium Gasoline，因此可先回傳 fuel_recommendation=premium；octane_aki=null，沒有從 Premium 推定最低辛烷值。plate_lookup=1、nhtsa_decode=1、epa_lookup=6。

`resolution.fuel_status` 與 `resolution.mpg_status` 分開。全部已核對候選的汽油類別相同才回傳 EPA 共識；類別不同仍需確認。未選定唯一配置時 vehicle=null，不將其中一筆 MPG 傳入計費。使用者確認 choices 後，可沿用相同州別／車牌，加入 vehicle_id 提交；會重新做一次車牌查詢。未知型號／不一致配置仍保持 no_match 或 needs_input，不猜配對。

原廠數字 AKI 的免費來源仍為原廠手冊／油箱蓋證據，本次沒有建立所有品牌手冊的自動擷取或完整 AKI 資料庫。


後續數字辛烷值規則已接入：E400 Coupe 候選共用原廠正常 91 AKI 建議，與未知油箱蓋最低值／臨時例外分開。站點數字下限及州別估計政策見 [辛烷值配對](octane-matching.md)。
