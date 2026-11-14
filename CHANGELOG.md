<!--
這個檔案是什麼：media-downloader 的改版紀錄，每個版本一節（Keep a Changelog 格式）。
使用者看得到的改動寫進 [Unreleased]；發版時改成 [x.y.z] - YYYY-MM-DD。
Release 說明從這裡取。
推上 GitHub：可以。公開前改寫成英文。
-->

# 改版紀錄

這個專案所有值得注意的改動都記在這裡。
格式依照 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本號依照 [語意化版本](https://semver.org/lang/zh-TW/)。

## [Unreleased]

### 新增

- 專案骨架：pywebview 視窗載入 React 介面，畫面顯示 App 名稱與後端連線狀態（繁體中文、英文）。
- 開發用指令 `scripts/dev.py`、一鍵檢查 `scripts/check.py`、CI 與 gitleaks 的 pre-commit 檢查。
- MIT 授權。
- 設計規範（`design-system/media-downloader/`）：視覺方向「唱片封套」、顏色與字體、各畫面的版面規則與中英文介面文案。
- 主畫面的靜態樣張：網址列、預覽、佇列與空畫面，使用假資料，可切換各種狀態與語言；按鈕還沒有作用。
- 介面字體隨 App 附帶（Noto Sans TC、Bricolage Grotesque），MP3 的縮圖顯示成正方形封面。
- 介面與後端的約定（`docs/介面與後端的約定.md`）：24 個指令、5 種事件與資料形狀。
- 後端的領域層：下載任務的狀態機（九種狀態）、錯誤代碼、下載進度的算法（MP4 的影像與聲音合成一條進度）、下載引擎的介面。還沒有接上介面。

### 變更

- 視窗預設大小改為 960x680，最小 720x520。

### 修正
