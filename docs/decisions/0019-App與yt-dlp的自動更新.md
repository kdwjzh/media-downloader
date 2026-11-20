<!--
這個資料夾是什麼：架構決策紀錄（ADR），一個重大決定一份（NNNN-標題.md，編號遞增）。
推上 GitHub：可以。維持中文（只有 README.md、CHANGELOG、CLAUDE.md 是英文，見 0021）。
-->

# 0019. App 的一鍵更新與 yt-dlp 的自動更新

- 日期：2026-11-19
- 狀態：已採用

## 背景

階段 5 決定發佈方式是 Inno Setup 安裝檔，加上 App 內的一鍵更新（`docs/階段5-計畫.md`）；yt-dlp 改成啟動時自動更新。
5b 要決定：版本號怎麼比、安裝檔從哪裡拿、怎麼核對、App 怎麼把自己換掉、更新途中出事會怎樣，以及 repo 還是私人的時候怎麼測。
作者看過設計後 13 項全部照建議（2026-11-19）。

查證（讀 Inno Setup 原始碼 `jrsoftware/issrc` 的 `Setup.MainFunc.pas`、`Setup.Install.pas`，並對過官方說明）：

- `InitializeSetup` 在 AppMutex 檢查**之前**執行。AppMutex 只檢查一次，找到就跳「請關閉 App」；加了 `/SUPPRESSMSGBOXES` 時這個框的預設答案是「取消」，安裝程式直接結束。
- 取消安裝時的「復原」只刪掉這次新放的檔案，不會把被換掉的檔案還原，`[InstallDelete]` 刪掉的 `_internal` 也不會回來：升級途中取消，App 會開不起來。
- `AllowCancelDuringInstall=no` 讓安裝階段的「取消」與關閉鈕無效；`/SILENT` 顯示進度視窗，`/VERYSILENT` 連它也不顯示；`[Run]` 的 `skipifsilent`／`skipifnotsilent` 依是否靜默略過該項；`{param:名稱|預設}` 讀命令列的 `/名稱=值`。
- GitHub 的 `releases/latest` 不回 pre-release。

## 決定

1. **版本號照語意化版本 2.0.0 比較**（`domain/version.py`）：`1.0.0-rc.1 < 1.0.0-rc.2 < 1.0.0-rc.10 < 1.0.0`；前面的 `v` 可有可無；`+` 之後的建置資訊接受但不比較、也不顯示。開頭補零、少一段、空的 pre-release 段都看不懂，看不懂一律當成沒有新版。
2. **安裝檔的網址由後端用版本號組出來**，不用 GitHub 回應裡的網址：`github.com/<repo>/releases/download/v<版本>/MediaDownloader-Setup-<版本>.exe`。版本號要先通過第 1 項的檢查，網址與檔名裡只會有它。
3. **檢查碼用發佈裡的 `.sha256` 檔**（同一個網址加 `.sha256`，打包腳本產生的那個）。格式不對、檔名不對、下載不完整都算不一致。不一致就刪掉、不執行，錯誤代碼是新加的 `checksumMismatch`（第 13 個，可以重試）。真正啟動前再算一次。
4. **轉址**：`http.py` 跟隨轉址，但最多 5 次，每一次的目標都重新檢查 https、預設連接埠、允許清單。下載安裝檔的清單是 `github.com`、`objects.githubusercontent.com`、`release-assets.githubusercontent.com`；刻意不放 `githubusercontent.com`（會連 `raw.githubusercontent.com` 也允許）。
5. **下載的檔案**放 `%LOCALAPPDATA%\media-downloader\updates`，先寫成 `.part`，核對過才改名；啟動時與失敗、取消時整個刪掉；解除安裝時也刪。上限 300 MB，每次讀取逾時 30 秒，沒有整體逾時（可以取消）。不做續傳。
6. **有下載在跑時，等安裝檔準備好才問**（不是按「立即更新」當下）。佇列沒有沒完成的項目就直接安裝。選「繼續下載」時設定頁留一顆「立即安裝」。
7. **啟動安裝程式**：`process.py` 的 `launch_detached()`，不放進我們的 Job，並要求離開 App 所在的 Job（不允許就不要求）；參數 `/SILENT /NORESTART /UPDATE=1`，不加 `/SUPPRESSMSGBOXES`。啟動後 App 照「確定關閉」的路徑停止下載並關窗。只有打包後才會啟動。
8. **安裝程式等 App 結束**：`/UPDATE=1` 時 `InitializeSetup` 每 0.2 秒看一次 App 的 mutex，最多 10 秒，並跳過 WebView2 檢查。10 秒後還在，就是 Inno 原本的「請關閉 App」框。裝完由 `[Run]` 的 `skipifnotsilent` 加 `Check: IsAppUpdate` 那一項重新開啟 App。
9. **`AllowCancelDuringInstall=no`**，手動安裝也一樣。
10. **yt-dlp 的自動更新**：只有打包後，`main.py` 在啟動後開一條 daemon 執行緒叫 `UpdateService.auto_update_engine()`。成功或已是最新版後 24 小時內不再做，失敗 1 小時（`engine-update.json`）。結果只寫記錄檔。更新與讀版本共用一把鎖：設定頁的「檢查更新」與版本會等它做完。
11. **`yt-dlp.exe.old` 由 App 刪**：每次啟動（`remove_stale_temp`）與每次更新成功後。被還在跑的下載鎖住時留到下次。
12. **測試用的更新來源**：`build_installer.py --test-update-source` 在 `build/` 放一個標記檔，PyInstaller 把它放進 `_internal`，App 看到它就改問 `http://127.0.0.1:8765`（只有這個位址可以用 http）。安裝檔叫 `…-TEST.exe`。不加選項時打包腳本確認 App 裡沒有標記，`test_update_source.py` 檢查三處的名字一致、只有選項會寫標記。伺服器是 `scripts/manual/serve_update.py`。
13. **畫面**：設定頁 App 那一列，有新版時「立即更新」取代「前往下載」；下載中有進度條、百分比與大小、「取消」；核對中是不確定進度條；失敗時說原因，給「重試」與「前往下載」。同一顆按鈕換文字與動作，焦點不會掉。確認視窗放在畫面外面（跟關閉確認一樣），更新可能在別的畫面時準備好。導覽列圓點不變。

## 理由

- 2、3：只有版本號來自網路，而且格式受限，網址與檔名就不可能被帶到別的地方。檢查碼跟安裝檔來自同一個發佈，擋得住下載損毀與傳輸中被改，擋不住 repo 本身被入侵（那要簽章，`階段5-計畫.md` 決定不簽）。`.sha256` 檔打包腳本本來就產生，本機測試只要放檔案，作者也能手動改壞它來驗。
- 6：等安裝檔的那段時間下載照跑；問的時候的數字就是會被停掉的數字；那段時間新加的項目也問得到。
- 7：不加 `/SUPPRESSMSGBOXES`：等不到 App 結束時要讓使用者看到框、自己關，而不是安裝程式默默結束、留下一台沒有 App 的電腦。
- 8：AppMutex 只檢查一次，App 關掉要一點時間（停止下載、清暫存）；在它之前等，才不會每次更新都跳框。
- 9：取消就會弄壞 App（見背景），不能取消比較安全。
- 10：開發時 `bin/` 的 yt-dlp 是錄測試樣本的那一版，不能自己變。共用一把鎖，設定頁不會在更新到一半時讀到舊版本。
- 11：yt-dlp 自己排的延遲刪除會被我們的 Job 一起結束（5a 實測）。
- 12：repo 是私人的，問 GitHub 只會 404。用標記檔而不是環境變數：正式版不讀任何外部設定就能決定來源。

## 考慮過的其他做法

- 用 GitHub API 的 `browser_download_url`：多一個來自網路的網址要檢查，換來的只是不用自己組。
- 用 API 的 `digest` 欄位：少下載一個小檔，但舊發佈沒有這個欄位，本機測試也要模擬 API 的整份回應。
- 按「立即更新」當下就問：作者原本的想法；問的數字可能跟真的停掉的不一樣，等下載的時間裡下載也得停。
- `/VERYSILENT`：看不到進度，不知道 App 為什麼不見了。
- 只在 App 叫起來的更新加 `/NOCANCEL`：手動升級時取消一樣會弄壞 App。
- 安裝到帶版號的資料夾（舊版留著，裝好才切換）：當機或斷電也不會壞，但等於重新設計安裝方式。
- 下載中斷時續傳：要處理伺服器支不支援、檔案換了怎麼辦；110 MB 重來一次可以接受。
- 自動更新 yt-dlp 成功時跳 toast：它在背景做，使用者不需要知道。

## 代價

- 安裝檔案的那約 10 秒內當機、斷電或被工作管理員結束，`_internal` 可能不完整，App 開不起來；要重新執行安裝檔（從 GitHub 下載）。設定、歷史、yt-dlp 都在安裝資料夾外面，不受影響。
- 安裝階段按不了取消（手動安裝也是）。
- App 在 10 秒內沒結束（例如關閉很慢），會跳 Inno 的「請關閉 App」框，要使用者動手。
- 開 App 後 20 秒內就進設定頁，版本的骨架佔位會等自動更新做完。
- rc 版如果在 GitHub 上標成 pre-release，`releases/latest` 不會回它，其他 rc 版看不到新版。5c 不發佈 rc，不受影響。
- 本機測試伺服器在 127.0.0.1，關掉 Wi-Fi 不會讓它斷線；真的斷網要等 5e 從 1.0.0 更新到 1.0.1 時測。改用「下載途中關掉測試伺服器」測連線中斷。
- 程式碼簽章沒有做，所以檢查碼只能證明檔案跟發佈裡的一樣。
- 改版本號時 `backend/uv.lock` 裡的版本也會跟著變（`uv run` 會改它），三處要一起改。
