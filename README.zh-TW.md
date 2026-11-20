<!--
這個檔案是什麼：media-downloader 的使用說明：是什麼、怎麼安裝、怎麼用、怎麼更新。
功能或使用方式有變就更新；README.md 和 README.zh-TW.md 一段對一段，要一起改。
推上 GitHub：可以。
-->

[English](README.md) | [繁體中文](README.zh-TW.md)

# Media Downloader

從 YouTube 下載音樂（MP3）與影片（MP4）的 Windows 桌面程式。可以一次貼很多個網址或整個播放列表，由下載佇列依序處理。

- 佇列：同時下載多個，每個項目有自己的進度；可以取消、重試、重新加入。
- 播放列表與頻道：列出全部影片，勾選要下載的。
- MP3 有 128／192／320 kbps，並嵌入封面；MP4 只列這支影片實際有的畫質。
- 下載完成的歷史紀錄；介面有繁體中文與英文。

## 系統需求

- Windows 10 或 11，64 位元。
- Microsoft Edge WebView2 執行階段。Windows 11 內建；較舊的 Windows 10 如果沒有，安裝程式會提示並告訴你去哪裡下載。
- 只支援、只測試 YouTube。

## 安裝

1. 打開 [Releases](https://github.com/kdwjzh/media-downloader/releases) 頁面，從最新版本下載兩個檔案：
   - `MediaDownloader-Setup-<版本>.exe`（安裝檔）
   - `MediaDownloader-Setup-<版本>.exe.sha256`（檢查碼）
2. 確認安裝檔沒有損壞或被改過（可以略過，建議做）。在下載的資料夾開 PowerShell：

   ```powershell
   (Get-FileHash .\MediaDownloader-Setup-<版本>.exe -Algorithm SHA256).Hash
   Get-Content .\MediaDownloader-Setup-<版本>.exe.sha256
   ```

   兩串長字串要相同（第一串是大寫，不影響）。Linux 或 macOS：`sha256sum -c MediaDownloader-Setup-<版本>.exe.sha256`（macOS 用 `shasum -a 256 -c …`）要顯示 `OK`。
3. 執行安裝檔。安裝檔沒有程式碼簽章，Windows 可能會出現藍色的「**Windows 已保護您的電腦**」視窗。按「**其他資訊**」，確認應用程式是 `MediaDownloader-Setup-<版本>.exe`（發行者會顯示「**不明的發行者**」），再按「**仍要執行**」。
4. 照安裝程式的步驟進行。只裝給目前的使用者，不需要系統管理員權限：
   - App：`%LOCALAPPDATA%\Programs\Media Downloader`
   - yt-dlp、FFmpeg、Deno：`%LOCALAPPDATA%\media-downloader\bin`
5. 從開始功能表開啟 **Media Downloader**。

## 使用方式

左側導覽有三個畫面：下載、歷史紀錄、設定。切換畫面時，原本的預覽、勾選與捲動位置都會保留。

### 貼網址與預覽

1. 複製 YouTube 影片的網址，在視窗裡任何地方按 Ctrl+V。也可以貼進「影片或播放列表網址」再按「查詢」或 Enter。
2. 預覽會顯示縮圖、標題、頻道與時長。選格式（MP3 或 MP4）與音質或畫質：
   - MP3：128、192、320 kbps。縮圖是正方形，成品會嵌入封面。
   - MP4：只列這支影片實際有的畫質。4K 是 VP9 編碼，部分播放器可能無法播放。
   - 下方顯示預估大小；沒有估計值時顯示「大小未知」。
3. 按「加入佇列」。

格式與畫質會記住上次用的。預覽還沒加入時又貼了另一個網址：已查到的會用當下選的格式自動加入佇列，還在查詢中的也會加入、查到後自動開始，查詢失敗的直接換成新的。

### 播放列表

貼上播放列表或頻道的影片頁網址，會出現勾選畫面：

- 預設全部勾選；可以用「全選」或逐列勾選。私人或已刪除的影片顯示「無法下載」，不能勾選。
- 整批用同一組格式與畫質。MP4 選的是上限（例如「最高 1080p」），每支影片取它有的、不超過上限的最高畫質。
- 按「將 N 個項目加入佇列」。按「取消」或 ✕ 回到主畫面，佇列不受影響。
- 只用鍵盤：Tab 進入清單，上下鍵移動、空白鍵勾選。
- 影片很多的列表要查比較久（上千支約十秒以上），等待時會顯示已經查了幾秒。

### 佇列

- 每個項目有自己的進度與目前階段（等待中、下載中、轉檔中、合併中）。同時下載數在設定裡改。
- 進行中或等待中的項目可以「取消」；已取消的可以「重新加入」；網路問題或未知錯誤失敗的可以「重試」。
- 「取消全部」會先跳出確認視窗。取消的項目要逐一按「重新加入」才會再排。
- 完成的項目可以「開啟資料夾」，檔案總管會選中那個檔案。
- ✕ 與「清除已結束的」只把項目從佇列拿掉，不會刪除檔案。
- 失敗時會說明原因與下一步（例如私人影片、地區限制、網路中斷）。未知錯誤的項目有「開啟記錄檔」，詳細原因在記錄檔裡。
- 還有項目沒完成時關閉視窗，會先確認；確定關閉後進行中與等待中的項目會停止，佇列不會保留。

### 歷史紀錄

下載完成的檔案都會列在這裡，最新的在最上面：

- 「重新下載」用當時的格式與畫質直接加入佇列。
- 「開啟資料夾」在檔案總管選中那個檔案；檔案已經不在時改開它原本所在的資料夾。
- 垃圾桶圖示刪除這筆紀錄；「清空紀錄」會先確認。兩者都只刪紀錄，不刪檔案。

### 設定

改了就生效，沒有儲存按鈕。

- 下載資料夾：按「變更…」選擇。佇列裡還沒完成的項目仍會存到原本的資料夾。
- 同時下載數：1 到 5，預設 3。
- 檔名重複時：略過、覆蓋（舊檔案會被取代，無法復原）或自動改名。
- 預設格式：MP3 音質與 MP4 畫質，跟預覽記住的是同一組。
- 語言：跟隨系統、繁體中文、English。
- 更新：見[更新](#更新)。
- 關於：版本、授權、使用的元件，以及「原始碼」與「開啟記錄檔資料夾」。

## 更新

- **Media Downloader**：有新版時，導覽列的「設定」旁會出現圓點。到設定按「立即更新」：App 會下載新版的安裝檔、核對 SHA-256、關閉、安裝，然後重新開啟。設定與歷史紀錄都會保留。還有下載在進行時會先問你。你按下之前不會下載任何東西。
- **yt-dlp**（實際從 YouTube 下載的程式）在 App 啟動時會在背景自動更新，一天最多一次。也可以在設定裡 yt-dlp 那一列按「檢查更新」（可能要二十秒左右）。YouTube 改了什麼、下載開始失敗時，通常更新它就會好。

## 解除安裝

打開 Windows 的「**設定 → 應用程式 → 已安裝的應用程式**」（Windows 10 是「**應用程式與功能**」），找到 **Media Downloader**，選「解除安裝」。解除安裝時會問要不要一併刪除設定、歷史紀錄與記錄檔；選「否」會保留，之後重新安裝還能使用。yt-dlp、FFmpeg、Deno 一律會刪除。下載的檔案不會被動到。

## 資料存在哪裡

| 內容 | 位置 |
| --- | --- |
| 設定與歷史紀錄 | `%APPDATA%\media-downloader` |
| 記錄檔 | `%LOCALAPPDATA%\media-downloader\logs` |
| yt-dlp、FFmpeg、Deno | `%LOCALAPPDATA%\media-downloader\bin` |
| 下載的檔案 | 你的「下載」資料夾，或設定裡選的資料夾 |

記錄檔不會記影片標題，路徑裡的使用者資料夾也會遮掉。

## 常見問題

**錯誤訊息是什麼意思？**

| 訊息 | 意思 |
| --- | --- |
| 這是私人影片 | 只有上傳者允許的人看得到。 |
| 這支影片有年齡限制／這是會員限定影片 | 要登入帳號才能看，目前不支援。 |
| 你的地區無法觀看這支影片 | 上傳者限制了可觀看的地區。 |
| 找不到這支影片／找不到這個播放列表 | 已被移除、設為私人，或網址有誤。 |
| 目前不支援直播 | 等直播結束、影片上架後再試。 |
| 不支援這個網站 | 只接受 YouTube 的網址。 |
| 連不上網路 | 檢查網路連線後按「重試」。 |
| 下載時發生未預期的問題 | 先重試；一直失敗時到設定更新 yt-dlp。「開啟記錄檔」可以看詳細原因。 |

**可以下載有年齡限制或會員限定的影片嗎？** 不行。這些要用你的帳號登入，這個 App 不做登入。

**可以用在其他網站嗎？** 只支援、只測試 YouTube。

**為什麼執行安裝檔時 Windows 會警告？** 安裝檔沒有程式碼簽章（憑證要每年付費）。照[安裝](#安裝)第 3 步略過；想確定檔案就是這裡發佈的那一個，可以核對 SHA-256。

**4K 影片播不出來。** YouTube 的 4K 是 VP9 編碼，部分播放器不支援。可以換 VLC 這類播放器，或改選 1080p。

## 使用條款

這個 App 只是工具。你要自行確認下載的內容與使用方式，在你所在的地區合法，並且符合下載來源網站的使用條款。只下載你有權下載的內容。

## 授權與第三方元件

Media Downloader 以 [MIT 授權](LICENSE)發佈。

安裝檔包含以下元件，各自依自己的授權：

| 元件 | 授權 | 說明 |
| --- | --- | --- |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | 從 YouTube 下載 |
| [FFmpeg](https://ffmpeg.org/) | GPL-3.0-or-later | 轉檔與合併；未經修改，取自 [yt-dlp/FFmpeg-Builds](https://github.com/yt-dlp/FFmpeg-Builds/releases/tag/autobuild-2026-10-31-18-18)。原始碼：[這個建置的 FFmpeg commit](https://github.com/FFmpeg/FFmpeg/tree/6d1bfd760916ab52814b950692d1c1635d29f3c7)與[建置腳本](https://github.com/yt-dlp/FFmpeg-Builds/tree/5ece62897c650b863c1ddda7b6964845344aef2d) |
| [Deno](https://github.com/denoland/deno) | MIT | yt-dlp 需要的 JavaScript 執行環境 |
| [Noto Sans TC](https://fonts.google.com/noto/specimen/Noto+Sans+TC) | OFL-1.1 | 字體 |
| [Bricolage Grotesque](https://github.com/ateliertriay/bricolage) | OFL-1.1 | 字體 |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause | App 的視窗（含微軟的 WebView2 SDK） |
| [truststore](https://github.com/sethmlarson/truststore) | MIT | 讓 Windows 驗證憑證 |

App 裡還有 Python 執行環境與其他 Python 套件，以及 React 等 npm 套件。上面這些和它們的授權全文，都在 App 安裝資料夾的 `licenses` 資料夾（`%LOCALAPPDATA%\Programs\Media Downloader\licenses`）。

## 文件語言

英文版 README、[CHANGELOG.md](CHANGELOG.md) 與 [CLAUDE.md](CLAUDE.md) 是英文；[`docs/`](docs/) 與 [`design-system/`](design-system/) 的設計文件是繁體中文。

## 開發

需要：Python 3.12 以上、[uv](https://docs.astral.sh/uv/)、Node.js（LTS）。

第一次先安裝依賴：

```bash
cd backend && uv sync && uv run pre-commit install
```

```bash
cd frontend && npm install
```

下載外部程式（yt-dlp、FFmpeg、Deno）到 `bin/`，並核對來源提供的 SHA-256；`bin/` 不進 git：

```bash
python scripts/fetch_binaries.py
```

啟動開發環境（同時啟動介面的開發伺服器與桌面視窗；關掉視窗就會一起結束）：

```bash
python scripts/dev.py
```

送出前跑一鍵檢查（後端與介面的 lint、型別檢查、測試）：

```bash
python scripts/check.py
```

打包安裝檔（需要 Inno Setup 7；從乾淨的狀態重新建置，安裝檔與 SHA-256 在 `packaging/output/`；開發伺服器要先關掉）：

```bash
python scripts/build_installer.py
```

發佈：版本號是 `backend/app/__init__.py` 的 `__version__`（由測試確保與 `pyproject.toml`、`uv.lock` 一致）。推 `v<版本>` tag 時，GitHub Actions 會跑檢查、打包安裝檔與 `.sha256`，並建立 draft Release，由人手動發佈。帶 `-rc.N` 的版本標成 pre-release。
