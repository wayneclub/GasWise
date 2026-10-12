# 車型要求與站點辛烷值配對

GasWise 的 `required_octane` 現在表示美國 AKI 的下限，使用 `station_rating >= threshold`，不是精確相等。已標示 93 的汽油可以符合 91 門檻。仍先核對汽油／柴油及請求油品類別；這次沒有新增跨所有汽油等級的上游價格抓取。

## 車型來源

`domain/vehicles/requirements.py` 為有來源、限年份／廠牌／型號／引擎／燃料的原廠規則入口。涵蓋 2018 Mercedes-Benz E400 Coupe／E400 4matic Coupe，以及下列已查驗的美國市場 2021 配置；不是全品牌辛烷值資料庫。

來源：[Mercedes-Benz 北美 2018 C238 COMAND 手冊](https://static.oneweb.mercedes-benz.com/css-oom-assets/en-ca/pdf/mercedes-e-class-coupe-2018-september-c238-comand-operators-manual-1.pdf)，汽油等級章節。手冊把 91 AKI 列為最高性能建議，另列 87 AKI 的臨時例外，絕對最低值仍要求參考油箱蓋。

回應分開保存 `recommended_octane_aki=91`、`minimum_octane_aki=null`、`temporary_octane_aki=87`、來源 URL 與限制。不能將臨時例外當成正常加油目標，也不能稱這段手冊證據證實油箱蓋絕對最低 91。原廠 normal target 不從 EPA Premium 推定。

選定 E400 vehicle_id 後，recommendations／smart search 自動套用正常 91 門檻；使用者設 93 則保持 93，設 87 不會降級正常車型目標。最低要求已確認時採最低值，最低未知才採正常建議值；臨時例外不進排名。未知配置的原廠最低值仍未知，新流程另提供有標示的用油估計。VIN 候選尚不唯一但共用相同規則時可先回報燃油資訊，不自行選 MPG。

### 2021 配置驗證

2026-10-10 實際取得免費 EPA 目錄資料，以下 MPG 是 EPA 綜合估計；較低於性能建議的油品不保證維持相同 MPG。

| 配置 | EPA ID | 綜合 MPG | 最低 AKI | 建議 AKI | 排名門檻 |
| --- | --- | --- | --- | --- | --- |
| C300 Sedan 後驅 | 43515 | 27 | 油箱蓋待確認 | 91 | 91 |
| C300 4matic Sedan | 43348 | 27 | 油箱蓋待確認 | 91 | 91 |
| X3 sDrive30i | 42849 | 27 | 89 | 91 | 89 |
| X3 xDrive30i | 42899 | 25 | 89 | 91 | 89 |
| X3 M40i | 42900 | 23 | 89 | 93 | 89 |
| M4 Coupe 手排 | 43559 | 19 | 91 | 93 | 91 |
| M4 Competition Coupe 自排 | 43560 | 19 | 91 | 93 | 91 |

來源：
- [2021 C-Class Sedan 美國原廠手冊](https://www.mbusa.com/content/dam/mb-nafta/us/owners/manuals/2021/Operators/MY21_C%20Sedan_OM.pdf)，Edition B-2021，p.371–372。87 僅為半箱臨時例外，須儘快補 premium，另有限速／轉速限制；未擴到 Coupe／Convertible。
- [2021 X3 原廠手冊鏡像](https://www.carmanualsonline.info/bmw-x3-2021-owners-manual/29)，US English 01405A10E93 VI/20，p.285。M Performance 為 M40i；未將這條套給完整 X3 M 或 PHEV。
- [2021 M4 Coupe 原廠手冊鏡像](https://manuals.plus/wp-content/uploads/2022/06/BMW_OwnersManual_01405A1E430-1-1.pdf)，US English 01405A1E430 X/20，p.344。M440i 是不同車型，不套 M4 規則。

這次驗證是文字選型／EPA 配置／原廠規則／合成站點排名；沒有這三台車的新車牌，不能稱為它們的真實車牌全鏈驗證。插電 X3 xDrive30e（43740）目前明確回傳不支援。

實際 GasWise `/v1/vehicles/resolve` handler 使用 live EPA：9 組請求皆 HTTP 200；三組不完整輸入要求確認車身／版本，六組確切配置成功解析。M4 候選沒有混入 M440i。完整回應保存在 `artifacts/2021-vehicle-resolution-live.json`。加上 2021 規則與最低門檻回歸後，全套 324 tests passed，Ruff 與 diff check 通過；排名仍為合成站點驗證。

### Hertz Car Sales 補充來源評估

Hertz 的 `Recommended fuel` 可補充建議 Regular／Premium，但不包含最低數字，不能直接轉成最低 87／91。已查到其 [2024 Expedition MAX 刊登](https://www.hertzcarsales.com/rent2buy/Ford/2024-Ford-Expedition-Max-37366318ac18486a980c6692a8a6d77b.htm)標示 Premium Unleaded，而 [Ford 2024 原廠指南](https://www.fordservicecontent.com/Ford_Content/Catalog/owner_information/2024Expedition_Quick_Reference_Guide_ENG_v1.pdf)明確允許最低 87、性能建議 91 以上。這顯示建議等級不能替代最低要求。

Hertz 刊登也依在售車輛而變，搜索可見舊刊登並不等於目前可 HTTP 取得。已接入可選的單刊登適配器；原廠數字規則仍優先，EPA 保留油耗來源。

`POST /v1/vehicles/fuel-assessment` 接受 `vehicle_id` 與可選 `hertz_listing_url`，回傳單一 `target_octane_aki`、`target_basis`、原始原廠建議、Hertz 狀態與來源。最低已確認用最低；最低未知但有正常原廠建議，回傳正常目標並明確標記。油品標籤不能證明原廠最低值，但可在明確標示下產生正常用油估計。

```json
{"vehicle_id":43559}
```

M4 回傳 target=91、basis=manufacturer_minimum，原始 recommendation=93 仍保留。C300 Sedan target=91、basis=manufacturer_normal_recommendation；X3 30i／M40i target=89、basis=manufacturer_minimum。評估的 target 與實際排序自動門檻一致；需要更高性能油品可設定 required_octane=93。

可選刊登僅接受固定 Hertz 主機上的 used／certified／rent2buy HTTPS `.htm` URL，不跟隨重新導向，最多讀 2 MB、一次請求。從可见文字取唯一 VIN／油品，透過既有 NHTSA → EPA crosswalk 核對選定配置；有歧義、不同年份或無法配對，不套用刊登。匹配是已知 VIN 欄位與 EPA 配置一致，不是原廠 build sheet 證明。Hertz 和原廠／EPA grade 衝突時保留原廠數字、回報差異。

EPA 快取按同一 vehicle ID 共用。現在另有按需的 Edmunds 型號／年份規格讀取及 Hertz 庫存發現，最多讀一個刊登；沒有全站爬取或持久化全球車型資料庫。原廠數字仍有明確覆蓋範圍。

### 按需規格評估（2026-10-10）

預設 `GASWISE_VEHICLE_SPECIFICATIONS_ENABLED=true`。未知車型不讀 PDF，而是從 EPA、Edmunds、Hertz 規格產生正常用油估計。關閉此設定回到原廠規則／EPA 等級、不推定數字的行為。

- Edmunds 預設 curl 模式以 v3 modelYears 動態取得車型／年份與 submodels，再讀 v5 批量配置 JSON；對應 features-specs 頁作 Referer。httpx 相容模式仍讀固定主機的 `/{make}/{model-family}/{year}/features-specs/`，保留 regular／premium recommended／premium required 的區分。family URL 只是發現入口，仍須核對年份、品牌、車型、引擎、汽缸、驅動、變速箱及已選版本；相關庫存提到相似版本不算匹配。
- Hertz 在預設 curl transport 下 POST 公開 `api/widget/ws-inv-data/getInventoryAndFacets`，參數包含年份／品牌／型號；httpx 相容模式仍讀 inventory HTML。最多取得兩筆庫存、只讀最多一個相符路徑刊登，解析 JSON-LD 及 `DDC.WS.state['ws-detailed-specs']['detailed-specs1']` 的 JSON 資料，不執行網站 JavaScript。JSON-LD 年份／品牌／型號、引擎等配置不符不參與比較。不同刊登皆歸 dealer_specs，不能靠同源車行堆票。
- 公開 HTTP 不帶 client Cookie／Authorization／API key，不跟隨重新導向；每頁最多 4 MB，curl 模式額外 HTTP 最多六次（Edmunds 一次 metadata、最多三個 submodel；Hertz 一次 inventory、一次詳細頁）；httpx 模式最多三次。成功規格按配置快取 24 小時，全部失敗時快取 15 分鐘；都是 process-local bounded cache。無付費 API、無登入、無 browser fallback、無持久化車型資料庫。
- 原廠數字優先。沒有原廠數字且分類一致，採明確標示的美國規劃值 Regular=87／Midgrade=89／Premium=91；依據 [EIA 典型分類](https://www.eia.gov/energyexplained/gasoline/octane-in-depth.php)。這是產品規劃政策，不證明車型最低 AKI；不同市場與要求更高辛烷值的例外仍須核對原廠證據。
- `source=specification_consensus` 代表不同來源組的等級一致，不代表已證明上游資料獨立。只有 EPA 可用時為 `source=fuel_grade_policy`、`assessment_status=single_source`。两種情況都保持 `manufacturer_requirement_verified=false`、`minimum_octane_aki=null`，並公開 unavailable／mismatch／ambiguous 的來源狀態。
- EPA Regular 搭配明确 Premium recommended，維持成本規劃的 Regular，不當成 required，也不算另一票證明 Regular。required 等級衝突則不推定數字；自動排名回 `vehicle_fuel_specification_conflict`，除非使用者明確選油品及 AKI。
- 車型／VIN／車牌回應帶同一份燃油評估。SearchService／SmartService 使用它的目標及警告；VIN MPG 候選不唯一時仍要求選配置。柴油不套 AKI。

`target_basis=specification_estimate` 明確區別估計與 `manufacturer_minimum`／`manufacturer_normal_recommendation`。來源細節在 `vehicle.fuel_recommendation.specification_evidence`，包含來源群組、配置匹配狀態、required／recommended 語義及原始標籤。非汽油、unsupported powertrain 或真實衝突仍可能沒有數字。

實測（FastAPI handler 使用真實 EPA HTTP）：

| 配置 | EPA ID | 目標 | 依據 |
| --- | --- | --- | --- |
| 2021 Camry LE/SE 2.5L FWD | 43305 | 87 | single_source 規劃估計 |
| 2021 Camry 3.5L FWD | 43302 | 87 | single_source 規劃估計 |
| 2021 X3 xDrive30i | 42899 | 89 | 已查驗原廠最低值 |
| 2021 M4 Competition | 43560 | 91 | 已查驗原廠最低值 |
| 2024 Expedition 2WD | 47167 | 87 | single_source 規劃估計 |

五組皆 HTTP 200，實際回應保存在 `artifacts/specification-assessment-live.json`。初次 httpx backend 實測的 Edmunds=403、Hertz=200 阻擋頁，兩者均正確列 unavailable；Hertz 後續純 HTTP transport 驗證已成功，見下節。匿名瀏覽器已讀到兩站真實欄位，證據在 `artifacts/edmunds-research/public-runtime-evidence.json` 與 `artifacts/hertz-research/discovery-findings.md`；這不等於 backend live 共識成功。

合成來源測試覆蓋一致／衝突／同源重複、Regular 與 premium recommended 相容性、required／recommended、配置與 gearbox 不符、誤用相關庫存、negative cache、credential isolation／redirect、main wiring 與 85 被排除／87、89 通過的合成排名。Hertz parser 使用已刪除識別資料的真實 inline fixture。未把合成共識／排名宣稱為 live 共識或油槍查驗。

HTTP smoke：Hertz C300 測試 URL 回 HTTP 200 但只有 1051 bytes／82 個可見文字字元，沒有 VIN 或 Recommended fuel，適配器回 hertz_ambiguous_listing，不宣稱 live Hertz 交叉驗證成功。留存 `artifacts/hertz-http-smoke.json`。直接 live EPA 的 fuel-assessment 四組回應留在 `artifacts/fuel-assessment-live.json`；合成 Hertz／NHTSA 測試驗證匹配、年份不符、grade 衝突、403／歧義／redirect。全套 340 tests passed，Ruff 通過。

## 站點地區與來源

優先採用站點 `octane` 的已標示 AKI。其次使用來源的站點州別、含州碼及 ZIP 的地址或既有加州來源線索；最後才用請求 `current_state`（美國州碼，例如 CA）。跨州時以站點所在地為準。缺州別不凭經緯度猜州；沒有新增付費地理編碼呼叫，也未實作 GPS 自動取得州別。

- 加州典型 Regular／Midgrade／Premium 分別為 87／89／91，來源為 [CEC Petroleum Watch](https://www.energy.ca.gov/sites/default/files/2025-05/2021-10_Petroleum_Watch_ada.pdf)。這是地區統計對應，不是每個油槍的保證。
- 其他美國州沒有已核對的個別州表時，使用保守全國區間：Regular 85–87、Midgrade 88–90、Premium 91–94。來源為 [EIA 等級定義](https://www.eia.gov/tools/glossary/index.php?id=Gasoline)及[典型等級說明](https://www.eia.gov/energyexplained/gasoline/octane-in-depth.php)。不是把每州 Premium 都標為 93。
- 推定依區間下端篩選，Premium 的 91–94 不能證明符合 93；已標示 93 的站點才可直接通過 93 門檻。
- 不把柴油套用汽油 AKI，也不改寫 `station.octane`。估計留在 `station.octane_inference` 與 `price_comparison.evidence[].octane_inference`，附來源、州別依據及 `station_verified=false`。

預設 `octane_policy=regional_estimate`，允許有來源地區估計參與排名並回傳警告。`verified_only` 僅接受站點已標示數字。政策也可在 smart rerank 改動，不重新抓取價格／路線。

```json
{
  "origin": {"lat": 34.03, "lng": -118.28},
  "vehicle_id": 38902,
  "current_state": "CA",
  "octane_policy": "regional_estimate"
}
```

`SearchResult.applied_octane_aki` 顯示實際門檻，`octane_policy` 顯示採用政策。付款、會員資格、價格新鮮度等篩選仍需另外符合。

## 驗證

真實 AutoZone → NHTSA → EPA 的 GasWise 車牌 handler 回傳 HTTP 200，E400 的 fuel_status=manufacturer_manual，recommended_octane_aki=91、temporary_octane_aki=87、minimum_octane_aki=null；MPG 仍需選後驅／4MATIC。

自動化測試覆蓋 89 不符合／91 與 93 符合、CA 典型值／CO 85 下端／州別優先權、93 門檻不接受 Premium 估計、油槍值優先、未知地區／車型、原廠規則不跨年份引擎車身套用、SearchService 自動套用目標，以及 strict snapshot rerank 零上游呼叫。價格排名使用合成 fixture，未將它宣稱為實際站點油槍驗證。


## 2026-10-10：Hertz 純 HTTP live 核對成功

預設 `GASWISE_VEHICLE_SPECIFICATIONS_TRANSPORT=curl`，使用 curl-cffi 0.16 的標準 Chrome TLS／HTTP profile；不啟動瀏覽器、不執行網站 JavaScript、不登入、不使用 API key、不讀取使用者 Cookie。每次請求都是全新 session，丟棄回應 Cookie、不跟隨 redirect、不重試；固定來源主機、最多 4 MB、15 秒 timeout。舊 httpx 模式可作基線比較。GasWise 自己的既有 API token 設定維持原狀，與來源網站認證無關。

公開 Hertz inventory POST 真實回傳 application/json，約 16 KB；其中只有 Gasoline 分類，建議油品須再讀一次詳細頁。Camry 詳細頁真實回傳約 617 KB，包含 2021 Camry SE、2.5L I4、FWD、8 speed automatic 與 Regular Unleaded。完整 equipment 陣列會夾雜沒有 spec 的分類列；解析器現會略過這些列並繼續讀取動力規格，不再提早中止。

實際 `/v1/vehicles/fuel-assessment` 結果：

| EPA id | 配置 | Hertz | 評估 |
|---|---|---|---|
| 43305 | 2021 Camry LE/SE 2.5L | matched／Regular | EPA + Hertz agreement，正常規劃目標 87 |
| 43302 | 2021 Camry 3.5L | mismatch | 不套用 2.5L 刊登，保留 EPA single_source |

兩組 API 均 HTTP 200。這是等級核對，不是原廠最低 AKI 驗證。Hertz 受目前在售庫存限制；沒有相符刊登時不保證任何車型都有回應。

Hertz 完成時的 Edmunds 基線仍未成功：普通 httpx/curl/profile 組合回 403、200 空物件，或約 2.4 KB 的 Akamai JavaScript 頁，沒有車型規格；當時回報 unavailable，沒有將驗證頁當成規格；後續正確 JSON Referer 組合已成功，且建立了實際三來源核對，見下一節。公開規格 API URL 與 fields 參數已從瀏覽器行為確認一致。

可重現：從 backend 執行 `uv run python ../scripts/smoke/smoke_public_specifications.py 43305 43302`。只輸出規格證據，不保存 Cookie/VIN。安全 live artifacts：`artifacts/specification-http-curl-live.json`、`artifacts/hertz-research/http-chrome-profile-probe.json`、`artifacts/edmunds-research/clean-tls-results.json`。這些結果只證明本次網路環境，不是來源永遠不封鎖的保證。


## 2026-10-10：Edmunds 動態純 HTTP JSON 已接入

新的成功請求組合：curl-cffi Chrome HTTP transport + `Accept: application/json` + 對應車型 specs 頁的 `Referer`，並正確傳遞 query params。逐項排除實測：Accept-only 與 tracking-metadata-only 都回空物件；Accept + Referer 回真實 1970 bytes style JSON。不需要 artifact/version/tracking headers，更不需要 Cookie、登入、API key、第三方 reader／翻譯中介或執行網頁 JavaScript。先前只能證明那些請求組合失敗，不能推論 Edmunds 必然需要認證。

流程：

1. `GET /gateway/api/vehicle/v3/modelYears`，參數 makeNiceId/modelNiceId/year。要求唯一 metadata，核對回應品牌／型號／年份，動態取得 submodels 和允許的 style IDs。
2. `GET /gateway/api/vehicle/v5/makes/{make}/models/{model}/submodels/{submodel}/years/{year}/styles/features-specs`，最多三個 submodel、每批最多 50 配置且僅接受完整的一頁。核對 `$dataset` 路徑與 style ID 來源。未持久化車型／style ID 對照庫。
3. 排除 EV/PHEV，再核對引擎、汽缸、驅動、變速箱與版本／車身詞。相同物理配置的多個 style 必須油品及 required/recommended 語意一致；不一致回 ambiguous，不選第一筆。

純 HTTP 動態探查實際取得 2021 Camry 13 配置、X3 4 個不同 style（含一個被排除的 PHEV）、M4 2 配置。公開來源資料保留在 `artifacts/edmunds-research/public-xhr-results.json`；測試 fixtures 僅保留配對必要欄位。

實際 GasWise handler 的 live 結果：

| EPA id | 車型配置 | Edmunds | Hertz | 目標來源 |
|---|---|---|---|---|
| 43305 | Camry LE/SE 2.5L | matched／Regular | matched／Regular | EPA + Edmunds + Hertz 一致；87 是正常規劃值 |
| 43302 | Camry 3.5L | matched／Regular | mismatch | EPA + Edmunds 一致；不套用 2.5L Hertz 刊登 |
| 42899 | X3 xDrive30i | matched／Premium recommended | unavailable | 保留原廠最低 89 |
| 43560 | M4 Competition Coupe | matched／Premium required | unavailable | 保留原廠最低 91 |

上述數字最低要求仍來自原廠規則，不從 Premium 標籤推導。Hertz 庫存／Edmunds URL family 覆蓋及來源限流仍有實際邊界；未知配置回報 mismatch／ambiguous／unavailable，不聲稱所有車型都保證可查。

完整 handler 回應：`artifacts/specification-http-edmunds-live.json`。可重現：從 backend 執行 `uv run python ../scripts/smoke/smoke_public_specifications.py 43305 43302 42899 43560`。
