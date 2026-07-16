# 開業雷達（newco-radar）— Landing Page 規格書

> 本文件自足：執行者不需要任何先前對話脈絡，照本文件做即可。
> 撰寫日期：2026-07-16。負責決策者：使用者本人（James）。

## 0. 專案背景（為什麼做這一頁）

產品構想：「每週把訂閱者指定縣市＋產業的**新設公司名單**寄到信箱」的訂閱服務。
買家是拿名單做業務開發的人：記帳士事務所、辦公設備商、電信門號業務、銀行開戶業務、商業保險業務。

**這一頁的唯一目的是驗證付費意願，不是做產品。**
驗證門檻：landing page 上線後貼到相關社團，收到 **10 個 email** 才進入產品開發；沒達標就停損。
因此：不寫後端、不做會員系統、不接金流，只做一頁靜態 HTML ＋一個 Google 表單連結。

## 1. 已驗證的資料事實（2026-07-16 實測，執行者不必重查）

以下事實已用 curl 實測通過，文案必須與這些事實一致，不得誇大：

1. 資料來源：政府資料開放平臺「公司設立登記清冊（月份）」（https://data.gov.tw/dataset/6047 ），每月更新，2013-02 起共 161 個月份檔。
2. 2026 年 6 月清冊實測：**全台 3,492 家新設公司**。欄位：統一編號、公司名稱、公司所在地、代表人、資本額、核准設立日期（民國年格式，如 1150529）。CSV、UTF-8 with BOM。
3. 營業項目由經濟部商工行政資料開放平臺 API 補齊（「公司登記基本資料-應用三」端點 `https://data.gcis.nat.gov.tw/od/data/api/236EE382-4942-41A9-BD03-CA0709025E7C?$format=json&$filter=Business_Accounting_NO eq {統編}`），回傳 Cmp_Business 陣列（代碼＋中文說明），免金鑰。
4. **名單不含電話與 Email**（政府公開資料本來就不提供）。這是誠實限制，文案必須明講。
5. 授權：依「政府資料開放授權條款」可自由加值利用，footer 必須放來源聲明。

取範例資料用（做網頁範例表格時抓真實資料，不要編造假公司）：

```bash
# 取得最新月份清冊下載連結
curl -s "https://data.gov.tw/api/v2/rest/dataset/6047" -H "Accept: application/json" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['result']['distribution'][-1]['resourceDownloadUrl'])"
# 下載後從 CSV 挑 3–4 筆不同縣市、資本額介於 10 萬～2000 萬的公司當範例
```

## 2. 交付物

### 階段一：Landing Page（本次交辦）

產出檔案（全部放在 `/home/pi/projects/newco-radar/`）：

| 檔案 | 說明 |
|---|---|
| `index.html` | 完整單檔靜態頁（inline CSS/JS，無任何外部 CDN 依賴），可直接丟 GitHub Pages / Cloudflare Pages |
| `README.md` | 部署步驟＋Google 表單連結替換說明 |

### 階段二：部署與發佈（2026-07-16 補充規劃，階段一完成後執行）

本專案是「筆電開發 → git push → 自動發佈」新工作流的第一個練手專案：純靜態頁，push 後由平台自動發佈，**完全不經過樹莓派**。

- [x] 2-1 `git init` ＋ 建 GitHub repo（2026-07-16：`gh repo create 0Zhen/newco-radar --public`，本地 main 分支已 push）
- [x] 2-2 接上 GitHub Pages（2026-07-16：`gh api` 啟用 Pages，來源 main 分支根目錄；網址 https://0zhen.github.io/newco-radar/ ，部署驗證見下方紀錄）
- [x] 2-3 使用者建 Google 表單（2026-07-16：`https://forms.gle/mK9MvVTf3712GGvM9`，已全域取代 `index.html` 內 2 處占位符並 push）
- [ ] 2-4 社團貼文文案（遵守 3.3 文案紅線）
- [ ] 2-5 email 數追蹤：驗證門檻 10 個 email，沒達標就停損不開發產品

開發機備註：若已改用筆電開發，clone 本 repo 到筆電即可，樹莓派上的目錄之後只做參考；Claude 設定移轉包見 `/home/pi/claude-code-migration-20260712.tar.gz`（搬遷當天重新打包，步驟見 `/home/pi/projects/laptop-dev-migration/PLAN.md` 第 3 節）。

## 3. 頁面規格

### 3.1 技術約束

- 單一 `index.html`，inline CSS，禁用外部 CDN（字型、JS 庫都不要）。
- `lang="zh-Hant"`，含 viewport meta、`<title>` 與 meta description。
- RWD：手機優先（目標受眾多從 FB 社團手機點進來）；寬表格用 `overflow-x: auto` 容器，頁面本體不得橫向捲動。
- 支援亮／暗色（`prefers-color-scheme`），用 CSS custom properties 做 token，兩個主題都要檢查對比度。
- 中文字型堆疊：內文 `"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif`；標題可用 `"Noto Serif TC","Songti TC",serif` 做明體對比。數字欄位加 `font-variant-numeric: tabular-nums`。
- 不用任何 framework，不寫 build step。JS 只允許少量（如 FAQ 摺疊），沒有也可以。

### 3.2 版面章節（由上而下）

1. **Hero**：
   - 主標（方向）：「每週一早上，你目標縣市＋產業的新設公司名單，寄到你的信箱。」可微調但必須含「每週」「縣市＋產業」「新設公司」三要素。
   - 副標：全台每月約 3,500 家新公司散在政府登記資料裡，開業雷達幫你篩出屬於你的那幾十家。
   - CTA 按鈕：「留下 Email，免費搶先體驗」→ 連到 Google 表單（見 3.4）。
2. **給誰用**：五個受眾卡片（記帳士／會計事務所、辦公設備與傢俱、電信與網路、銀行開戶與收單、商業保險），每個一句「為什麼開業頭 30 天是你的黃金接觸期」。
3. **你每週會收到什麼**：範例表格，欄位＝統編、公司名稱、縣市、代表人、資本額、營業項目。**用第 1 節指令抓的真實資料 3–4 筆**，表格下方註明「節錄自 2026 年 6 月經濟部公司設立登記清冊（真實資料）」。
4. **先說清楚**（誠實區塊，三點）：
   - 名單不含電話與 Email——政府公開資料本來就沒有，我們給的是精準開發標的，不是電話簿。
   - 資料 100% 來自政府公開資料，依政府資料開放授權條款合法利用。
   - 我們做的是「幫你省下每月翻 3,500 筆的時間」：篩選、補營業項目、整理成可直接用的格式。
5. **定價與 CTA**：「正式上線後預計 NT$299/月。現在留下 Email：免費收到依你條件篩好的第一份名單，正式上線後早鳥半價。」再放一次同一顆 CTA。
6. **FAQ**（3–4 題）：資料合法嗎／多久寄一次／可以退訂嗎／為什麼沒有電話欄位。
7. **Footer**：資料來源聲明（經濟部商工行政資料開放平臺、政府資料開放平臺，依政府資料開放授權條款利用）＋「本服務與經濟部無隸屬或背書關係」。

### 3.3 文案紅線（不可違反）

- 不得宣稱或暗示名單含電話、Email、或「可直接撥打的客戶名單」。
- 不得暗示政府官方合作或背書。
- 價格一律寫「預計」，因為尚未定價。
- 不得使用「保證成交」「穩賺」類字眼。
- 全部使用繁體中文，語氣務實不浮誇。

### 3.4 Email 收集方式

- CTA 連結先放占位符 `https://forms.gle/REPLACE_ME`，在 `index.html` 內以明顯註解標示 `<!-- TODO: 替換成正式 Google 表單網址 -->`。
- README.md 說明：使用者要自己建一個 Google 表單（欄位：Email、想收哪個縣市、想收哪類產業、你的行業），建好後全域取代占位符。

## 4. 驗收標準（做完逐項自檢，寫進交付報告）

- [ ] `index.html` 單檔開啟即可完整顯示，無外部網路請求（可用瀏覽器 devtools 或 `grep -E 'https?://' index.html` 檢查，僅允許 CTA 表單連結與 footer 來源連結）。
- [ ] 手機寬度（375px）與桌面寬度下版面皆正常，無橫向捲動。
- [ ] 亮／暗色兩主題皆可讀，範例表格在兩主題下對比清楚。
- [ ] 範例表格為真實資料且已註明出處。
- [ ] 3.3 文案紅線逐條核對通過。
- [ ] CTA 占位符與 TODO 註解存在，README 有替換說明與部署步驟。
- [ ] 不得偽造「已有 N 位訂閱者」等不實社會證明。

## 5. 執行注意

- 本專案獨立於 crypto-bot / freqtrade-quant / telegram-reminder-bot，不要動那些目錄。
- 不需要 sudo、不需要裝套件；若真的需要下載範例資料，只用 curl + python3 標準庫。
- 完成後在本檔案末尾補一節「## 6. 階段一完成紀錄」：日期、自檢結果、遺留事項。

## 6. 階段一完成紀錄

**日期：2026-07-16**

產出：`index.html`、`README.md`（皆已放在 `/home/pi/projects/newco-radar/`）。

範例表格資料來源：即時下載 2026 年 6 月「公司設立登記清冊」（data.gov.tw dataset 6047，共 3,492 家，欄位與 PLAN.md 記載一致），挑出 4 筆不同縣市、資本額 10 萬～500 萬的真實公司，並用 GCIS 應用三 API 補齊營業項目：信順報關（桃園）、寶揚應用材料（新北）、弼呈工程（基隆）、合美環保（新竹縣）。

自檢結果（對照第 4 節逐項）：

- [x] `index.html` 單檔開啟即可完整顯示，無外部網路請求——`grep -E 'https?://' index.html` 僅命中 2 處 CTA 表單占位連結，無 CDN／字型／追蹤請求。
- [x] 手機寬度（375px）與桌面寬度下版面皆正常，無橫向捲動——用 chromium headless 截圖＋注入 `scrollWidth`/`clientWidth` 量測腳本驗證，兩種視窗寬度下皆 `scrollWidth == clientWidth`（無溢出）；版面用 `overflow-x:auto` 表格容器＋`auto-fit/1fr` 卡片格線，無寫死超寬元素。
- [x] 亮／暗色兩主題皆可讀——`prefers-device-scale-factor` 與 `--force-dark-mode` 截圖比對，內文與強調色對比清楚。
- [x] 範例表格為真實資料且已註明出處——表格下方註明「節錄自 2026 年 6 月經濟部公司設立登記清冊（真實資料）」。
- [x] 3.3 文案紅線逐條核對通過——無誇大電話/Email 名單宣稱、無政府背書暗示、價格皆標「預計」、無「保證成交」類字眼、全繁中且語氣務實。
- [x] CTA 占位符與 TODO 註解存在，README 有替換說明與部署步驟——`https://forms.gle/REPLACE_ME` × 2，README 含 sed 取代指令與 GitHub Pages／Cloudflare Pages 部署步驟。
- [x] 不得偽造「已有 N 位訂閱者」等不實社會證明——未使用任何社會證明文案。

遺留事項：Google 表單尚未建立（占位符待使用者建表單後取代）；階段二（git init／建 repo／接部署平台）尚未執行，待使用者確認後進行。
