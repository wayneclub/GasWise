# VIN 解碼與 EPA 車型對應

VIN 不是單靠一個公式就能算出所有配置。格式、檢查碼是本機可驗證的；品牌／車型／引擎等需製造商申報的編碼對照資料。資料庫可以在本機部署，不一定要每次呼叫外部 API。

已使用官方 **NHTSA vPIC**，無需 AutoZone 私有服務或 Google key。服務仍有自動流量控制，不能宣稱無限查詢。[官方 API](https://vpic.nhtsa.dot.gov/api/)、[本機資料庫下載](https://vpic.nhtsa.dot.gov/Downloads)。目前沒有安裝本機 VIN 資料庫。

## GasWise API

`POST /v1/vehicles/vin`，使用現有 Bearer token：

```json
{
  "vin": "完整17碼VIN",
  "model_year": 2018
}
```

`model_year` 可省略；官方建議已知時提供年份，降低 VIN 年份循環解讀的歧義。只接受 17 個 ASCII 字元、不含 I/O/Q；小寫自動轉大寫。目前對應範圍是美國 EPA 1984 年起的受支援車型；部分 VIN／非美國市場配置可能無法對應。

流程：

1. 呼叫 NHTSA `DecodeVINValuesBatch`，一次只送一個 VIN。
2. 檢查回傳 VIN 身份、解碼錯誤碼與檢查碼；不把不完整回應當成完整配置。
3. 品牌／年份／車型／series／trim 對應 EPA 目錄；已知車身、引擎排量／汽缸、驅動、變速箱資訊用於排除不相容候選。
4. 唯一可用 EPA 配置才回傳 `vehicle.id`、MPG 與建議油種。
5. 配置仍不唯一或缺引擎資訊時，回傳 `choices`，下一次以同 VIN 加 `vehicle_id` 確認。指定 ID 必須仍與已知解碼欄位相容，不能強制選擇另一台車。

EPA 對應最多五個車型、十個配置詳情；超過上限改用文字選車。`upstream_calls` 是邏輯操作次數，EPA 快取命中可能無 HTTP；每次 VIN 提交都有一個 NHTSA 請求，沒有保留 VIN 快取。NHTSA 或 EPA 失敗不自動重試，也沒有隱藏付費來源 fallback。

回應狀態：

| status | 意義 |
| --- | --- |
| resolved | 找到唯一且與已知欄位一致的 EPA 配置 |
| needs_input | 仍需確認配置，不自動選第一筆 |
| partial | 解碼不完整、缺少關鍵欄位或檢查碼未通過 |
| no_match | 找不到可靠 EPA 對應；使用文字選車 |
| unsupported | EV、PHEV、其他燃料或目錄範圍外 |

即使解碼成功也不是原廠完整 build sheet：缺少的選配、變速箱或車型細節不會被填成事實。NHTSA 不直接提供 MPG 或最低辛烷值；MPG 與 Premium／Regular／Diesel 由 EPA 車型紀錄提供，原廠最低 AKI 仍標為未驗證。

拿回 `vehicle.id` 後可直接送到 recommendations／smart search，省略 MPG 與油種。Smart snapshot 保存的是 EPA 車型資料，沒有包含完整 VIN；重新排名仍無需 VIN 查詢。

VIN 透過本機 POST body 與 NHTSA POST body 送出，不放入查詢 URL；成功回應只顯示尾四碼。後端不另記錄 VIN body、不持久化 VIN 查詢歷史；基礎設施另行啟用 body logging 的行為不在此承諾內。

## 驗證證據

2026-10-10，官方 HTTP 範例的部分 VIN 模式 `5UXWX7C5*BA` 成功回傳 BMW X3／2011／xDrive35i 等欄位。此回應帶錯誤碼 6，不作完整身份驗證。

再使用相同公開模式、合成序號及本機計算的檢查碼，成功取得錯誤碼 0 並完成 EPA 對應：ID `31056`、2011 BMW X3 xDrive35i、3.0 L／6 缸／AWD、自排、Premium、19／26／21 MPG。這是編碼與跨來源串接驗證，並未查驗某台真實車輛的出廠配置。

模擬測試驗證格式、檢查碼、回傳身份、年份不匹配、429 不重試、部分解碼不查 EPA、EV／PHEV 排除、唯一／不唯一候選、已知配置衝突、API 遮罩回應與無 VIN URL。
