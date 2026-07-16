# 開業雷達（newco-radar）

「每週把訂閱者指定縣市＋產業的新設公司名單，寄到信箱」訂閱服務的 landing page。
目前階段：**驗證付費意願**，只有一頁靜態 HTML，尚未開發產品本體。詳細背景與驗收標準見 `PLAN.md`。

## 檔案

- `index.html`：完整單檔 landing page，inline CSS/JS，無外部 CDN 依賴，可直接開啟或部署到任何靜態託管平台。

## 上線前必做：替換 Google 表單連結

`index.html` 內目前有 2 處 CTA 連結是占位符：

```
https://forms.gle/REPLACE_ME
```

上線前請：

1. 建立一個 Google 表單，欄位建議：
   - Email
   - 想收哪個縣市
   - 想收哪類產業
   - 你的行業（記帳士／設備商／電信／銀行／保險／其他）
2. 表單發佈後複製正式網址。
3. 在 `index.html` 內全域取代 `https://forms.gle/REPLACE_ME`（可用編輯器的「全部取代」，或指令）：

   ```bash
   sed -i 's#https://forms.gle/REPLACE_ME#你的正式表單網址#g' index.html
   ```

4. 取代後用 `grep -n "REPLACE_ME" index.html` 確認沒有殘留占位符。

## 部署步驟（GitHub Pages）

1. 在此目錄執行：

   ```bash
   git init
   git add index.html README.md PLAN.md .gitignore
   git commit -m "Add newco-radar landing page"
   ```

2. 到 GitHub 建一個新 repo（public 或 private 皆可，本 repo 無機密資訊），依提示 `git remote add origin ...` 後 `git push -u origin main`。
3. 到 repo 的 Settings → Pages，Source 選擇 `main` 分支、根目錄 `/`，儲存。
4. 等幾分鐘，GitHub 會給一個 `https://<帳號>.github.io/<repo>/` 網址，打開確認 index.html 正常顯示即為部署成功。
5. 之後每次 `git push` 到 main，幾分鐘內網址會自動更新（不需要碰樹莓派）。

若改用 Cloudflare Pages：連接同一個 GitHub repo，Build command 留空、Build output directory 填 `/`（因為是純靜態檔案，無需建置），其餘流程相同。

## 驗證門檻

Landing page 上線並貼到相關社團後，收到 **10 個 email** 才進入產品開發；沒達標就停損，不繼續投入。
