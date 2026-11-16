# 設計規範：Media Downloader

> 定案日期：2026-11-13（階段 2）
> 視覺方向：「唱片封套」。背景見 `docs/decisions/0006`。
> 做任何畫面前先讀這份；`pages/<畫面>.md` 有寫的以它為準。
> 能顯示什麼資料、不要設計什麼，以 `docs/介面設計依據.md` 為準，這裡不重複。

## 1. 個性

像翻唱片行的架子：封面是主角，介面本身安靜。大膽的地方只有一個，就是**縮圖的形狀代表格式**（第 6 節）。其他地方保持克制，不加裝飾。

## 2. 顏色

元件裡只用語意變數，不寫色碼。變數定義在 `frontend/src/index.css` 的 `@theme`；加深色模式時只換這張表的值。

| 變數 | 名字 | 色碼 | 用途 |
|---|---|---|---|
| `--color-bg` | 淡紫白 | `#F7F4F8` | 視窗背景、導覽列 |
| `--color-surface` | 白 | `#FFFFFF` | 佇列項目、預覽、輸入框、設定區塊 |
| `--color-text` | 墨紫 | `#231A24` | 主要文字；MP4 標籤底色 |
| `--color-text-muted` | 灰紫 | `#655A68` | 次要文字、提示文字、圖示 |
| `--color-accent` | 梅紫 | `#6B2D5C` | 主按鈕、進度條、連結、焦點框、勾選框 |
| `--color-accent-hover` | 深梅紫 | `#57234B` | 主按鈕滑過 |
| `--color-accent-soft` | 淡梅紫 | `#EFE6F0` | 目前所在的導覽項、列滑過、已勾選的列 |
| `--color-on-accent` | 白 | `#FFFFFF` | 梅紫、墨紫、磚紅底上的文字 |
| `--color-highlight` | 芥末黃 | `#F2C230` | 只當 MP3 標籤的底色，上面放墨紫字 |
| `--color-success` | 松綠 | `#1F6B45` | 「完成」的圖示與文字 |
| `--color-danger` | 磚紅 | `#B3261E` | 失敗、錯誤訊息、破壞性按鈕 |
| `--color-danger-soft` | 淡磚紅 | `#FBEAE8` | 錯誤訊息區塊的底色 |
| `--color-border` | 邊框紫灰 | `#877A8A` | 輸入框、下拉選單、勾選框、次要按鈕的邊框 |
| `--color-divider` | 分隔線 | `#E5DEE7` | 列與列之間的線、進度條的軌道、骨架佔位 |

### 對比（WCAG 公式計算）

| 前景／背景 | 數值 | 門檻 |
|---|---|---|
| 墨紫／淡紫白 | 15.47 | 4.5 |
| 墨紫／白 | 16.87 | 4.5 |
| 墨紫／淡梅紫 | 13.86 | 4.5 |
| 墨紫／芥末黃 | 10.07 | 4.5 |
| 灰紫／淡紫白 | 5.99 | 4.5 |
| 灰紫／白 | 6.53 | 4.5 |
| 灰紫／淡梅紫 | 5.36 | 4.5 |
| 梅紫／淡紫白 | 8.93 | 4.5 |
| 梅紫／白 | 9.74 | 4.5 |
| 梅紫／淡梅紫 | 8.00 | 4.5 |
| 梅紫／分隔線（進度條／軌道） | 7.39 | 3 |
| 白／梅紫 | 9.74 | 4.5 |
| 白／深梅紫 | 12.02 | 4.5 |
| 白／墨紫 | 16.87 | 4.5 |
| 白／磚紅 | 6.54 | 4.5 |
| 白／磚紅 90%（確認視窗危險按鈕滑過，疊在白底上） | 5.51 | 4.5 |
| 松綠／白 | 6.47 | 4.5 |
| 松綠／淡紫白 | 5.93 | 4.5 |
| 磚紅／白 | 6.54 | 4.5 |
| 磚紅／淡紫白 | 5.99 | 4.5 |
| 磚紅／淡磚紅 | 5.61 | 4.5 |
| 邊框紫灰／白 | 4.05 | 3 |
| 邊框紫灰／淡紫白 | 3.72 | 3 |

限制：

- 芥末黃在白底上只有 1.68，**不能當文字、圖示、邊框或進度條**。
- 分隔線在白底上只有 1.32，只能當裝飾線，**不能當控制項的邊框**。
- 新增顏色或新的前景／背景組合時，先算對比再加進這張表。

## 3. 字體

| 角色 | 字體 | 用在哪裡 |
|---|---|---|
| 標題字 | Bricolage Grotesque（可變字體），中文退到 Noto Sans TC | 頁面標題、格式標籤（MP3／MP4）、主按鈕 |
| 內文字 | Noto Sans TC（可變字體） | 其他所有文字 |

- 兩個字體都**隨 App 附帶**（npm 套件 `@fontsource-variable/bricolage-grotesque`、`@fontsource-variable/noto-sans-tc`，授權皆為 OFL 1.1），不從網路載入。關於頁與 README 要列出。
- 備援順序：`"Microsoft JhengHei UI", "Segoe UI", sans-serif`。
- 會跳動的數字（百分比、大小、速度、剩餘時間、時長）加 `font-variant-numeric: tabular-nums`。

| 層級 | 大小／行高 | 字重 | 用途 |
|---|---|---|---|
| 頁面標題 | 20／28 | 600 | 「歷史紀錄」「設定」、播放列表標題 |
| 預覽標題 | 16／24 | 500 | 預覽區塊的影片標題、空畫面的標題 |
| 內文 | 14／20 | 400 | 一般文字、輸入框、按鈕 |
| 項目標題 | 14／20 | 500 | 佇列、歷史、播放列表的標題 |
| 輔助 | 12／16 | 400 | 狀態列、頻道、時長、說明文字、格式標籤（600） |

不用小於 12px 的字。標籤與標題不用全大寫（MP3、MP4 本身是縮寫，例外）。

## 4. 間距、圓角、層次

- 間距只用 4 的倍數：4、8、12、16、24、32。頁面內距 24；列的內距 12；列與列之間 0（用分隔線）。
- 圓角依層級不同：格式標籤 4、縮圖 6、輸入框與次要按鈕 8、清單容器與預覽區塊 10、主按鈕為膠囊形（999）。
- 不用陰影。層次靠「白色區塊放在淡紫白背景上」。只有確認視窗用一層半透明遮罩（`rgb(35 26 36 / 0.45)`，變數 `--color-scrim`）。
- 圖層：內容 0、固定的按鈕列 10、提示文字 20、確認視窗 40。

## 5. 版面

- 視窗預設 960 x 680，**最小 720 x 520**（2026-11-16 在真視窗看過後維持，見 `docs/decisions/0006`）。這是含標題列與外框的大小：網頁實際拿到約 947 x 645 與 707 x 485。
- 左側導覽列固定 88px：下載、歷史紀錄、設定。每項是圖示加文字，目前所在頁用淡梅紫底加梅紫字，並設 `aria-current="page"`。三個畫面的導覽位置相同。
- 主要內容區內距 24。清單寬度跟著視窗；設定頁內容寬度上限 640。
- 不出現水平捲軸。只有清單本身可以垂直捲動，頁面不另外捲。
- App 有新版時，導覽列的「設定」旁出現一個梅紫圓點（附無障礙名稱「有新版」），不彈窗。

## 6. 元件

### 縮圖（這個設計的特色）

- **MP3 的縮圖裁成正方形**（52 x 52，取中央），**MP4 維持 16:9**（92 x 52）。形狀就代表格式。
- 縮圖欄固定寬 92，正方形靠左，所以標題的左緣永遠對齊。
- 一律設定寬高，載入前顯示分隔線色的佔位。`alt` 留空（旁邊有標題），載入失敗時維持佔位。
- 預覽區塊的縮圖放大一級：正方形 96 x 96，16:9 為 160 x 90。切換格式時形狀跟著變。

### 格式標籤

- MP3：芥末黃底、墨紫字。MP4：墨紫底、白字。12px、字重 600、內距 2 x 8、圓角 4。
- 標籤一定有文字，不靠顏色分辨。

### 按鈕

| 種類 | 樣子 | 用在哪裡 |
|---|---|---|
| 主要 | 梅紫底白字、膠囊形、高 36 | 每個畫面只有一顆：「加入佇列」「將 N 個項目加入佇列」 |
| 次要 | 白底、邊框紫灰、墨紫字、圓角 8、高 32 | 查詢、重試、開啟資料夾、重新下載、變更… |
| 文字 | 無底無框、梅紫字 | 清除已結束的、取消（列內） |
| 危險 | 白底、磚紅邊框與字；確認視窗內為磚紅底白字 | 清空紀錄 |
| 圖示 | 28 x 28 的點擊範圍、灰紫圖示 | ✕（從佇列移除／關閉預覽）、刪除這筆紀錄 |

- 所有按鈕用 `<button>`。只有圖示的按鈕要有 `aria-label` 和滑過提示。
- 按鈕文字不截斷、不換行；寬度依文字，最小寬 64。中英文都要放得下。
- 滑過：底色變化 150ms。按下：不改變大小。停用：透明度 0.45、`disabled` 屬性、游標 `not-allowed`。
- 執行中的按鈕（查詢、檢查更新）換成進行式文字並停用。

### 焦點

- 所有可操作元件在鍵盤操作時顯示 2px 梅紫外框，外推 2px（`focus-visible`）。不移除外框。
- Tab 順序等於視覺順序：導覽列 → 網址輸入框 → 預覽 → 佇列。
- 固定的按鈕列不可遮住有焦點的列（清單加 `scroll-padding-bottom`）。

### 輸入框與選單

- 高 36、白底、邊框紫灰、圓角 8。每個欄位都有看得見的 `<label>`。
- 提示文字用灰紫色，只放範例，不取代標籤。
- 格式切換（MP3｜MP4）與同時下載數是並排的單選按鈕（`role="radiogroup"`），選中的用梅紫底白字。

### 進度條

- 高 6、圓角 3、軌道用分隔線色、填色用梅紫。
- **確定**：寬度等於真實百分比，`role="progressbar"` 加 `aria-valuenow`。
- **不確定**：一段 30% 寬的梅紫色塊左右來回，1.6 秒一輪、線性。`role="progressbar"` 不帶數值，旁邊一定有階段文字。
- 從下載進到轉檔或合併時，立刻換成不確定樣式並拿掉所有數字，不停在 100%。
- 完成、失敗、已取消、排隊中不顯示進度條，但位置保留，列高不變。

### 清單的列

- 佇列、歷史紀錄用同一種列：縮圖欄 92、標題一行（截斷加省略號，`title` 屬性放完整標題）、狀態一行、進度條一行。**列高固定 72**，任何狀態都不變。
- 列與列之間用分隔線；整個清單包在一個白底、圓角 10 的容器裡。
- 每列最多一顆文字按鈕加一個圖示按鈕。
- 列內的按鈕在很多列重複出現，`aria-label` 要帶上項目標題（例如「取消: 標題」），螢幕閱讀器才分得出是哪一列的。
- 失敗的列沒有進度條，錯誤訊息可以用掉那個位置顯示成兩行（列高不變），窄視窗時下一步才不會被截斷。
- 項目用穩定的 id 當 key。超過 100 列時用虛擬清單。

### 錯誤訊息

- 兩行：第一行是發生什麼事（磚紅、字重 500、前面加警告圖示），第二行是下一步（墨紫）。
- 顯示在出問題的地方（預覽的位置、佇列的那一列），不放在畫面頂端。
- 預覽區的錯誤用 `role="alert"`；佇列狀態變化放在 `aria-live="polite"` 的區域。
- 重試沒用的錯誤不放重試按鈕。任何訊息都不提登入。

### 確認視窗

- 只用在不可逆的動作：清空紀錄、還有下載沒完成時關閉視窗。更新通知不用視窗。
- 用瀏覽器內建的 `<dialog>` 加 `showModal()`：焦點鎖在視窗內、Esc 關閉、關閉後焦點回到原本的地方。
- 預設焦點在「放棄這個動作」的按鈕上。這顆按鈕通常叫「取消」；但如果「取消」會被讀成相反的意思，就改用說清楚結果的詞（關閉確認用「繼續下載」，因為「取消」會被讀成取消下載）。
- 淡入 150ms；內建的 `<dialog>` 關閉時立刻消失，沒有淡出。

### 短暫提示（toast）

用在動作做完了、但結果跟預期不同，又不值得放進某一列的時候（例如開啟資料夾時找不到檔案、貼上的不是網址）。

- 主內容區底部置中，距底 16。墨紫底、白字、14px、圓角 8、內距 8 x 12，前面一個 Phosphor `Info` 圖示（16）。不加陰影。
- 圖層 20。`role="status"`，不搶焦點，沒有關閉按鈕。
- 同一時間只有一則，新的取代舊的。顯示 5 秒；滑鼠停在上面時暫停計時。
- 淡入 150ms；減少動態時不做。
- 不用來報錯誤：錯誤顯示在出問題的地方（見「錯誤訊息」）。

### 錯誤邊界

- 兩層：主內容區一層（導覽列與關閉確認不在裡面，壞掉時照常可以用），整個 App 一層。
- 壞掉時顯示：警告圖示、`crash.title`、`crash.body`、主按鈕 `crash.reload`（重新載入網頁；佇列在後端，重新載入後拿得回來）。
- 關閉確認放在主內容區那層的外面。連它也壞掉時它不再訂閱 `closeRequested`，`api/` 會直接關閉視窗，所以視窗一定關得掉。

### 圖示

- 一律用 Phosphor（`@phosphor-icons/react`）的 regular 粗細，大小 16 或 20。不用表情符號當圖示。
- 文字旁的裝飾圖示加 `aria-hidden`。

## 7. 動態

- 會一直動的只有兩種：不確定進度條、查詢中的骨架佔位（透明度 1 ↔ 0.5，1.2 秒）。
- 顏色變化 150ms；確認視窗與 toast 淡入 150ms（沒有淡出，見第 6 節）。不做清單項目的進場動畫。
- `prefers-reduced-motion: reduce` 時：不確定進度條改成整條 40% 透明度的靜態色塊，骨架不閃動，淡入淡出取消。

## 8. 文案規則

- `<html lang>` 要跟著介面語言切換（影響螢幕閱讀器的發音與中文字形）。
- 所有文字放 `frontend/src/i18n/zh-TW.json` 與 `en.json`，鍵名見各畫面的文案表。元件裡不寫死字串。
- 英文用句首大寫（Add to queue），不用每字大寫。
- 按鈕用動詞開頭，說清楚按了會發生什麼。
- 錯誤訊息不道歉、不用驚嘆號、不出現程式的原始錯誤文字。
- 數字與單位之間空一格（62 %例外，寫成 62%）；大小用 MB／GB，預估值前加「約」（英文加「~」）。

### 同一個動作只用一個詞

| 動作 | 中文 | English | 不要用 |
|---|---|---|---|
| 把項目放進佇列 | 加入佇列 | Add to queue | 下載、開始、確定 |
| 停止進行中或排隊中的項目 | 取消 | Cancel | 停止、中止 |
| 失敗後再試一次 | 重試 | Retry | 再試、重新整理 |
| 已取消的項目再排一次 | 重新加入 | Add again | 重試、恢復 |
| 把已結束的項目從佇列拿掉 | 移除 | Remove | 刪除、清除（單筆） |
| 一次拿掉所有已結束的項目 | 清除已結束的 | Clear finished | 清空 |
| 歷史紀錄再抓一次 | 重新下載 | Download again | 重試 |
| 刪掉一筆歷史紀錄 | 刪除這筆紀錄 | Delete this entry | 移除 |
| 刪掉全部歷史紀錄 | 清空紀錄 | Clear history | 全部刪除 |
| 在檔案總管顯示成品 | 開啟資料夾 | Open folder | 顯示、瀏覽 |
| 查網址的資訊 | 查詢 | Look up | 搜尋、解析 |

「取消」在確認視窗和播放列表勾選畫面也代表「放棄這個動作」，這是一般慣例，不算衝突。

### 共用文案

| 鍵 | 中文 | English |
|---|---|---|
| `nav.downloads` | 下載 | Downloads |
| `nav.history` | 歷史紀錄 | History |
| `nav.settings` | 設定 | Settings |
| `nav.updateAvailable` | 有新版 | Update available |
| `format.mp3` | MP3 | MP3 |
| `format.mp4` | MP4 | MP4 |
| `format.label` | 格式 | Format |
| `quality.audioLabel` | 音質 | Audio quality |
| `quality.videoLabel` | 畫質 | Video quality |
| `quality.kbps` | {{n}} kbps | {{n}} kbps |
| `quality.upTo` | 最高 {{n}}p | Up to {{n}}p |
| `quality.exact` | {{n}}p | {{n}}p |
| `size.approx` | 約 {{size}} | ~{{size}} |
| `size.unknown` | 大小未知 | Size unknown |
| `action.addToQueue` | 加入佇列 | Add to queue |
| `action.cancel` | 取消 | Cancel |
| `action.retry` | 重試 | Retry |
| `action.addAgain` | 重新加入 | Add again |
| `action.remove` | 從佇列移除 | Remove from queue |
| `action.openFolder` | 開啟資料夾 | Open folder |
| `action.openLog` | 開啟記錄檔 | Open log file |

### 錯誤訊息（預覽與佇列共用）

鍵名對應後端的 `ErrorCode`。第一行是 `title`，第二行是 `hint`。

| 鍵 `error.*` | 中文 title／hint | English title／hint | 重試鈕 |
|---|---|---|---|
| `invalidUrl` | 這不是有效的網址／請確認網址是完整的，並以 https:// 開頭。 | This isn't a valid URL／Check that the URL is complete and starts with https://. | 無 |
| `unsupportedSite` | 不支援這個網站／目前只支援 YouTube 的影片和播放列表。 | This site isn't supported／Only YouTube videos and playlists are supported for now. | 無 |
| `notFound` | 找不到這支影片／影片可能已被移除，請確認網址是否正確。 | Video not found／It may have been removed. Check that the URL is correct. | 無 |
| `private` | 這是私人影片／只有上傳者允許的人看得到，目前無法下載。 | This video is private／Only people the uploader allows can see it, so it can't be downloaded. | 無 |
| `ageRestricted` | 這支影片有年齡限制／目前不支援這類影片，無法下載。 | This video is age-restricted／Videos like this aren't supported yet, so it can't be downloaded. | 無 |
| `membersOnly` | 這是會員限定影片／目前不支援這類影片，無法下載。 | This video is for members only／Videos like this aren't supported yet, so it can't be downloaded. | 無 |
| `geoBlocked` | 你的地區無法觀看這支影片／上傳者限制了可觀看的地區，無法下載。 | This video isn't available in your region／The uploader restricted where it can be watched, so it can't be downloaded. | 無 |
| `playlistNotFound` | 找不到這個播放列表／列表可能是私人的或已被刪除，請確認網址。 | Playlist not found／It may be private or deleted. Check the URL. | 無 |
| `liveNotSupported` | 目前不支援直播／等直播結束、影片上架後再試。 | Live streams aren't supported／Try again after the stream ends and the video is published. | 無 |
| `playlistUrl` | 這是播放列表的網址／請重新貼上這個網址，等清單出現後再勾選要下載的項目。 | This is a playlist URL／Paste it again and wait for the list, then pick what to download. | 無 |
| `network` | 連不上網路／請檢查網路連線後重試。 | Can't connect／Check your internet connection, then retry. | 有 |
| `unknown` | 下載時發生未預期的問題／可以重試；如果還是不行，記錄檔裡有詳細資訊。 | Something unexpected went wrong／You can retry. The log file has details. | 有，另有「開啟記錄檔」 |

`ageRestricted` 與 `membersOnly` 的說法刻意不提登入（第一版沒有這個功能）。`liveNotSupported` 是設計時加的。`playlistUrl` 是階段 3c 加的，只會出現在佇列：預覽還沒查完就被自動加入的網址，查出來是播放列表。後端的 `ErrorCode`（`backend/app/domain/errors.py`）用的就是這 12 個鍵名，改的時候兩邊一起改。

## 9. 交付前檢查

- [ ] 每個文字與背景的組合都在第 2 節的對比表裡
- [ ] 元件裡沒有寫死的色碼和字串
- [ ] 只用鍵盤可以完成：貼網址 → 加入佇列 → 取消／重試 → 開啟資料夾
- [ ] 每個可操作元件有看得見的焦點框
- [ ] 只有圖示的按鈕有無障礙名稱
- [ ] 每個狀態都有文字，不只靠顏色
- [ ] 佇列項目在所有狀態下高度相同
- [ ] 視窗縮到 720 x 520 時沒有水平捲軸、按鈕文字沒有被截斷
- [ ] 中文和英文都看過一次
- [ ] 開啟「減少動態」後沒有持續的動畫
- [ ] 沒有出現 `docs/介面設計依據.md` 第 5 節列的東西
