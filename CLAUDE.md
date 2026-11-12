<!--
這個檔案是什麼：media-downloader 的專案規格書兼工作規則。
Claude Code 每次開工會自動讀。
規格或決定有變就更新；踩到坑就把「以後不要這樣做」寫成規則。
推上 GitHub：可以，但不能放 token、個人路徑或帳號資料。公開前改寫成英文。
程式和這份文件不一致時，要嘛改程式，要嘛改這份；以這份為準。
-->

# CLAUDE.md：media-downloader

以抓音樂為主、影片為輔的 Windows 桌面下載器，用下載佇列一次處理多首歌和整個播放列表。

這份放決定與規則。細節在 `docs/功能規格.md`、`docs/架構.md`，決定的背景在 `docs/decisions/`。
`docs/` 與這份衝突時以這份為準，並把 `docs/` 改成一致。文件沒寫到的功能先問，不要自行擴充。

## 1. 目標

- 取代舊專案 youtube-downloader（Python + CustomTkinter），解決它難維護與實際使用時的 bug。
- 主要用途是抓音樂（MP3），偶爾抓影片（MP4）；可以一次排很多個網址，也可以整個播放列表下載。
- 使用者是作者本人，以及從 GitHub 下載安裝檔的其他人。他們不一定有裝 Python。
- 先支援 YouTube；架構預留其他平台（TikTok、Instagram、X、Telegram 等）。
- 同時作為 UI 設計流程的練習專案。

### 不做的事

- 格式轉換器。
- 圖片教學的說明視窗、選單列（文件／關於／檢查更新併入設定頁）。
- 第一版不測試、不保證 YouTube 以外的平台。
- 第一版不做：MP3 自動填標籤、原始音訊格式（m4a／opus）、深色模式、歷史搜尋、Windows 通知、字幕、時間區段裁剪、瀏覽器 cookies 登入。
- App 不做背景靜默更新；有新版只在介面內提示。
- 不用「下載 zip + 跑 bat」的方式發佈。

## 2. 決定

| 項目 | 決定 | 理由 |
| --- | --- | --- |
| 名稱 | repo `media-downloader`，App 顯示名稱 Media Downloader | 看得出用途，不綁單一平台 |
| 語言／框架 | 後端 Python 3.12+；介面 React + TypeScript + Vite + Tailwind | 下載邏輯留在 Python；介面用網頁技術才能套用 UI 設計流程。見 `docs/decisions/0001` |
| 桌面外殼 | pywebview（Windows 上用 WebView2） | 單一程序、兩種語言，比 Tauri 好維護。見 `0002` |
| 下載引擎 | 呼叫 yt-dlp 官方執行檔，搭配 Deno 與 FFmpeg；不 `import yt_dlp` | yt-dlp 可獨立更新、取消就是結束程序。見 `0003` |
| 外部程式位置 | 安裝檔採「僅目前使用者」安裝到 `%LOCALAPPDATA%\Programs`，外部程式放在安裝資料夾 | yt-dlp 自我更新需要資料夾可寫入。見 `0005` |
| 介面狀態 | Zustand | 輕量，佇列狀態集中管理 |
| 介面語言 | 繁體中文、英文，react-i18next，預設跟隨系統 | 給別人用 |
| 儲存 | 設定用 JSON、歷史紀錄用 SQLite，放 `%APPDATA%` | SQLite 是 Python 內建，之後好做搜尋 |
| 測試 | 後端 pytest、介面 Vitest | |
| 打包／發佈 | PyInstaller（資料夾模式）+ 安裝檔；推 tag 時由 GitHub Actions 打包上傳 Releases | 使用者不需安裝 Python |
| 實作順序 | 骨架 → 技術驗證 → UI 設計 → 後端 → 介面 → 打包 | UI 設計時要有真實資料當依據。見 `0004` |
| 授權 | MIT；附帶的 yt-dlp、FFmpeg、Deno 維持各自的授權，README 與關於頁要列出 | 個人工具，最簡單寬鬆 |
| 公開 | 開發期間不公開，完成後公開；公開前文件改成英文 | |

套件版本在動手時查當下的穩定版，不憑記憶寫。

## 3. 規格

完整內容與舊版 bug 對照表見 `docs/功能規格.md`。第一版範圍：

- 下載佇列：連續貼多個網址，每個項目獨立進度、可取消、可重試；可設定同時下載數。
- 播放列表：貼網址後展開成佇列項目，可勾選要下載哪些。
- 格式 MP3、MP4；畫質／音質依該影片實際可用的選項列出，顯示預估檔案大小。
- 影片資訊預覽（縮圖、標題、時長、頻道）；音樂檔可嵌入封面。
- 記住上次的格式、畫質、路徑。
- 歷史紀錄：重新下載、開啟所在資料夾、刪除單筆、清空。
- 設定頁：下載路徑、預設格式與畫質、同時下載數、重複檔處理、介面語言、檢查更新、關於。
- 重複檔處理：略過／覆蓋／自動改名。
- 錯誤訊息分類說明原因與下一步（私人影片、年齡限制、會員限定、地區限制、網路中斷）。
- yt-dlp 可獨立更新；App 有新版時在介面內提示，不用彈窗。
- 進度是一條總進度：下載 → 轉檔／合併，並顯示目前階段。
- 安裝檔內含所有外部程式；執行時不出現主控台視窗。

畫面：主畫面（貼網址 + 佇列）、空狀態、播放列表勾選、歷史紀錄、設定。

完成的定義：`docs/功能規格.md` 第 2 節的舊版問題（U1–U4、C1–C11）逐項驗過。

## 4. 架構

細節見 `docs/架構.md`。

```
介面 frontend/  →  橋接 bridge/  →  服務 services/  →  領域 domain/  ←  基礎設施 infrastructure/
```

```
backend/app/
  bridge/            介面與後端之間的轉接，不含業務邏輯
  services/          佇列、影片資訊、歷史、設定、更新
  domain/            資料模型與規則：DownloadTask（狀態機）、MediaInfo、ErrorCode、MediaEngine 介面
  infrastructure/
    engines/ytdlp/   YtDlpEngine，實作 MediaEngine
    storage/         設定檔、歷史紀錄資料庫
    binaries/        外部程式的路徑與版本
    logging/
backend/tests/
frontend/src/
  api/               唯一呼叫橋接層的地方
  pages/ components/ stores/ i18n/
design-system/       UI 設計規範（MASTER.md 與 pages/）
docs/                功能規格、架構、決策紀錄、技術驗證
packaging/           PyInstaller 設定、安裝檔腳本
scripts/             一鍵檢查、下載外部程式、開發用指令
```

### 依賴方向（不可違反）

1. 上層可以呼叫下層，下層不可 import 上層。
2. 下層要通知上層時只發事件，不直接呼叫。
3. `domain/` 不碰檔案、網路、子程序。
4. 只有 `infrastructure/engines/ytdlp/` 可以出現 yt-dlp 的參數、輸出格式、錯誤字串。
5. `bridge/` 不放業務邏輯。
6. 介面只有 `frontend/src/api/` 可以呼叫橋接層，其他元件一律透過它。
7. 外部程式的路徑只能從 `infrastructure/binaries/` 取得。
8. 下載任務的狀態只能由 `DownloadTask` 的狀態機改變。
9. 後端回傳錯誤代碼（`ErrorCode`），不回傳給人看的文字；文字放在介面的語言檔。

新增檔案前先說明它屬於哪一層。需求看起來要打破上述規則時，停下來問。

### 多平台

下載引擎實作 `MediaEngine` 介面。第一版只有 `YtDlpEngine`。`MediaInfo` 帶 `platform` 欄位。
程式內部不拿「youtube」當通用名稱（類別、資料表、設定鍵）；YouTube 只是其中一個平台。

## 5. 規則

### 安全

- token、cookies、帳號資料、個人路徑不進 git，也不寫進記錄檔。
- 外部執行檔（yt-dlp、FFmpeg、Deno）不進 git，由 `scripts/` 下載；下載後核對來源提供的雜湊值。
- 呼叫外部程式一律用參數清單，不用字串拼接的 shell 指令；使用者輸入的網址與路徑只能當成單一參數傳入。
- 檔名取自影片標題時要清掉 Windows 不允許的字元，並確認結果仍在使用者選的下載資料夾內。

### 測試

- 每個 bug 先寫會失敗的測試重現，這個測試永久保留。
- 完成前一定要跑過一鍵檢查腳本 `scripts/check.py`。
- `domain/` 與 `services/` 的邏輯要有 pytest 測試；測試不連網路，yt-dlp 的輸出用錄下來的樣本。

### 工作流程

- 一次只做一個功能或修正；開工前先說會改哪些檔案。
- 使用者看得到的改動寫進 `CHANGELOG.md` 的 `[Unreleased]`。
- 重大決定寫進 `docs/decisions/NNNN-標題.md`。
- 照第 2 節的實作順序一個階段一個階段做，不跨階段；每個階段結束時說明怎麼驗收。

### 介面文字

- 顯示給使用者的文字都放在 `frontend/src/i18n/` 的 `zh-TW.json` 與 `en.json`，兩份同步新增。
- 元件裡不寫死中文或英文字串。
- `README.md` 和 `README.zh-TW.md` 要一起改。

### 外部程式

- 呼叫任何外部程式都要隱藏主控台視窗，並以 UTF-8 處理輸出。
- yt-dlp 的參數查官方文件確認，不憑記憶寫。
- 呼叫 yt-dlp 的坑（依據見 `docs/技術驗證.md`）：
  - 一律帶 `--ignore-config`、`--encoding utf-8`、`--color never`、`--ffmpeg-location`；不加 `--encoding utf-8` 輸出會是系統的 cp950。
  - Deno 用 `--js-runtimes deno:<絕對路徑>` 指定；相對路徑會找不到。
  - `--print` 會進入安靜模式，要下載進度就得再加 `--progress`。
  - 取消要結束整棵程序樹：`yt-dlp.exe` 是兩層程序，只結束外層，內層和 FFmpeg 會繼續跑。
  - 失敗的結束代碼一律是 1，錯誤分類靠 stderr 的 `ERROR:` 文字。

### UI 工作流程（ui-ux-pro-max + frontend-design）

本專案框架：react
設計規範檔：`design-system/media-downloader/MASTER.md`（畫面專屬規則在 `pages/` 底下，會覆寫 MASTER）

做任何 UI 前：

1. 先讀 MASTER.md；有對應的 `pages/<畫面>.md` 就以它為準。
2. 用 ui-ux-pro-max 查規則：`--stack react`、`--domain web`、`--domain ux`。
3. 不要自行重新產生 design system 或用 `--force` 覆寫 MASTER.md，要改先問。

視覺決策：

- 配色、字體、版面、動畫多寡、介面文案依 frontend-design。
- ui-ux-pro-max 的 `--design-system` 只當候選；它給的落地頁版型在 App 畫面中忽略。

規則衝突時：

- 無障礙、平台慣例、框架寫法依 ui-ux-pro-max。
- 配色、字體、版面、動畫多寡、介面文案依 frontend-design。
- 作者明講的需求優先於兩者。

交付前：

- 文字對比 4.5:1、可點擊區域夠大、焦點可見、尊重減少動態設定。
- 按鈕文字說清楚動作，同一動作全流程用同一個詞。
- 錯誤訊息說明哪裡錯、怎麼修；空畫面要引導下一步。
