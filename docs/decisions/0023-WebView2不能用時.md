<!--
這個資料夾是什麼：架構決策紀錄（ADR），一個重大決定一份（NNNN-標題.md，編號遞增）。
推上 GitHub：可以。維持中文（只有 README.md、CHANGELOG、CLAUDE.md 是英文，見 0021）。
-->

# 0023. WebView2 不能用時先說明再結束

- 日期：2026-11-27
- 狀態：已採用

## 背景

5e 在 Windows Sandbox 碰到：WebView2 的登錄 `pv` 寫 157.0.4341.60，`EdgeWebView\Application` 裡只有 158.0.4370.33。安裝程式只看登錄，所以過得去；App 開起來是白色視窗，沒有任何說明。

查證結果（pywebview 6.2.1）：

1. pywebview 只看登錄的 `pv`（≥ 86）就選 Edge Chromium，不看檔案在不在。
2. WebView2 在視窗建好後才非同步初始化；失敗時 `platforms/edgechromium.py` 的 `on_webview_ready` 用 logger `pywebview` 記一筆 error 就 `return`。不丟例外、不退回 MSHTML，視窗留著，`webview.start` 要等使用者關窗才返回。
3. 登錄完全沒有 `pv` 時，pywebview 會退回 MSHTML，介面一樣不能用。

記錄檔「亂碼」：`app.log` 其實是正確的 UTF-8。Windows PowerShell 5.1 的 `Get-Content` 沒加 `-Encoding` 時，用系統的字碼頁（繁體中文是 cp950）讀沒有 BOM 的檔案，中文就亂了（Sandbox 實測）。

## 決定

1. 開視窗前，`main.py` 用 `infrastructure/webview2.py` 呼叫 WebView2 loader 的 `GetAvailableCoreWebView2BrowserVersionString`（loader 是 pywebview 附的 `WebView2Loader.dll`，路徑由 `main.py` 給，因為只有它認識 pywebview）。
2. 失敗時：記錄檔寫下 HRESULT 與 Windows 的說明，顯示雙語訊息框（是／否），按「是」用 `shell.py` 開微軟的下載頁（同 `installer.iss`），然後結束。訊息最後附錯誤碼，方便回報。
3. loader 本身載入不了時當作「無法判斷」：只寫記錄檔，照常開視窗。
4. 記錄檔改用 `utf-8-sig`：新檔案開頭有 BOM，接著寫與重新開啟都不會再加。
5. 安裝程式的檢查不改。

## 理由

- loader 的這個函式跟真正啟動時用的是同一套尋找邏輯，也會照 `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER`。Sandbox 實測：原樣回 `0x80070002`，設了環境變數回 158。
- 事前檢查不用等待、不用逾時，慢電腦不會被誤判。
- 安裝完預設會勾「開啟 App」，App 立刻就會說明；安裝程式不用再有第二份判斷。
- 有 BOM 的 UTF-8，PowerShell 5.1、記事本和其他工具都會自己判斷編碼。

## 考慮過的其他做法

- 事後偵測（攔 pywebview 那行 error，或掛 .NET 的 `CoreWebView2InitializationCompleted`）：要依賴 pywebview 內部的英文字串或屬性，升級時可能默默失效。代價是初始化的其他失敗（例如資料夾沒有權限）仍然是白畫面，目前沒遇過。
- 逾時（網頁幾秒內沒回報就緒）：慢電腦沒驗證過（階段 5 交接 #12），抓太短會關掉能用的 App，抓太長使用者要盯著白窗很久。
- 安裝程式確認 `Application\<pv>` 資料夾存在：要猜安裝位置，猜錯會誤擋（預設按鈕是「否」）。安裝程式也呼叫 loader：判斷一樣，但要把 DLL 包進安裝程式並對 32／64 位元，同一套邏輯會變兩份。
- 亂碼只改測試步驟（`-Encoding UTF8`）：一樣有做，但使用者自己看記錄檔時不會知道要加。

## 已知代價

- 1.0.1 以前留下的 `app.log` 沒有 BOM，要等它輪替（1 MB）才換成有 BOM 的新檔。
- 微軟的 Evergreen 安裝程式能不能修好「登錄在、檔案不在」沒驗證過（Sandbox 裡沒修好）。
