# 主畫面（貼網址、預覽、佇列、空狀態）

> 門面畫面。共用規則見 `../MASTER.md`；這裡寫的優先。

## 版面

由上到下三塊：網址列（固定）→ 預覽區塊（有預覽時才出現）→ 佇列（佔滿剩下的高度，自己捲動）。查到的是播放列表或頻道時，預覽區塊和佇列換成勾選畫面（`pages/playlist.md`），網址列還在。

```
│ 影片或播放列表網址                                           │
│ ┌──────────────────────────────────────────────┐ ┌────────┐ │
│ │ https://www.youtube.com/watch?v=…            │ │  查詢  │ │
│ └──────────────────────────────────────────────┘ └────────┘ │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ┌────────┐  （標題）                                     ✕│ │
│ │ │ 縮圖   │  （頻道）　（時長）                            │ │
│ │ └────────┘  格式 [ MP3 | MP4 ]   音質 [ 320 kbps ▾ ]      │ │
│ │             約 1.6 MB                      [ 加入佇列 ]   │ │
│ └──────────────────────────────────────────────────────────┘ │
│ 佇列（6）                                       清除已結束的 │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ┌────┐  （標題）                                MP3      │ │
│ │ │封面│  （狀態列）                                       │ │
│ │ └────┘  （進度條）                        [按鈕]    ✕    │ │
│ ├──────────────────────────────────────────────────────────┤ │
```

## 網址列

- 標籤「影片或播放列表網址」一直看得見。`<input type="url">`，不自動完成、不拼字檢查。
- 在視窗內任何地方按 Ctrl+V，貼上的內容像網址時立刻查詢（2026-11-16 定案）：
  - 聽 `paste` 事件，不讀剪貼簿（WebView2 讀剪貼簿可能跳權限詢問）。
  - 焦點在其他輸入框或下拉選單時不攔；確認視窗開著時不攔。
  - 焦點在網址框：框是空的就立刻查詢；框裡有字就是一般的貼上。
  - 「像網址」：去掉前後空白後不是空的、中間沒有空白或換行、有「.」、2048 字以內。真正合不合法由後端判斷。
  - 不像網址時不查詢，顯示 toast `toast.notUrl`；沒有文字（例如圖片）時什麼都不做。原因：誤貼一段文字也會把上一個預覽自動加入佇列。
- 按 Enter 或「查詢」也會查詢。輸入框是空的時候「查詢」停用。
- 查詢開始後輸入框清空，方便貼下一個。

## 預覽區塊

- 高度固定 172（三種狀態都一樣），出現和消失時佇列往下／往上移一次，之後不再跳動。
- 右上角 ✕ 是「關閉預覽」，任何狀態都可以按；查詢中按下會放棄這次查詢。

| 狀態 | 顯示 |
|---|---|
| 查詢中 | 縮圖與兩行文字的骨架佔位、「正在查詢影片資訊…」、網址（太長時在中間換行，不撐破版面）。`aria-busy="true"`。超過 5 秒多一行 `preview.slow`（見 `pages/playlist.md`「查詢很久的時候」） |
| 查到了 | 縮圖、標題（最多兩行）、頻道、時長、格式切換、音質或畫質選單、預估大小、主按鈕「加入佇列」。焦點移到「加入佇列」 |
| 查詢失敗 | 淡磚紅底；警告圖示、錯誤 title、hint、網址。可重試的錯誤有「重試」；未知錯誤另有「開啟記錄檔」。`role="alert"` |
| 是直播 | 同查詢失敗的樣式，用 `error.liveNotSupported` |

查到了的細節：

- 格式與音質／畫質帶入上次用的值。收到 `settingsChanged` 時，使用者還沒動過的預覽跟著換；動過的保留使用者的選擇。
- 影片沒有影像（選項裡沒有 MP4）時，MP4 停用。
- 按「加入佇列」或 ✕ 之後，焦點回到網址框。
- 選 MP3：縮圖正方形、選單標籤「音質」、選項 128／192／320 kbps。
- 選 MP4：縮圖 16:9、選單標籤「畫質」、**只列這支影片實際有的畫質**。上次存的畫質高於這支影片的最高畫質時，選這支的最高畫質。直式影片用短邊當畫質。
- 預估大小一律加「約」；沒有估計值時顯示「大小未知」。切換格式或畫質時跟著更新。
- 選 2160p 時，選單下方多一行輔助文字（`preview.note4k`）。這行出現時不能改變預覽區塊的高度。

### 預覽還沒加入時又貼了另一個網址

（2026-11-13 決定，選項 B）

| 舊預覽的狀態 | 處理 |
|---|---|
| 已查到 | 用當下選好的格式與音質／畫質自動加入佇列，然後預覽新的 |
| 還在查詢中 | 也加入佇列，以「正在查詢影片資訊…」的狀態顯示，查到後自動開始；查詢失敗時錯誤顯示在佇列的那一列 |
| 查詢失敗 | 直接換成新的，不進佇列 |
| 是播放列表的勾選畫面 | 直接換成新的，不進佇列（2026-11-17 決定） |

自動加入時在 `aria-live` 區域宣告 `queue.autoAdded`。

## 佇列

- 標題「佇列（N）」，N 是全部項目數。右側「取消全部」只在有還沒結束的項目時顯示；「清除已結束的」只在有完成、失敗或已取消的項目時顯示。
- 超過 100 列時用虛擬清單（MASTER「清單的列」）。
- 新項目加在最下面。同時下載數以外的項目顯示「等待中」。
- 列的版型見 MASTER 第 6 節。各狀態的內容：

| 狀態 | 狀態列 | 進度條 | 按鈕 |
|---|---|---|---|
| 排隊中 | 等待中 | 無 | 取消 |
| 查詢資訊中 | 正在查詢影片資訊…（標題的位置顯示網址，縮圖是佔位） | 不確定 | 取消 |
| 準備下載（輪到之後還沒有任何進度：`doneBytes` 是 0 且沒有 `totalBytes`） | 準備下載… | 不確定 | 取消 |
| 下載中 | 下載中 62%　599 / 966 MB　8.4 MB/s　剩 44 秒 | 確定 | 取消 |
| 下載中、沒有百分比 | 下載中　118 MB　2.1 MB/s | 不確定 | 取消 |
| 連線中斷重試中 | 連線中斷，重試中（第 2 次） | 維持中斷時的百分比 | 取消 |
| 轉檔中（MP3，含嵌入封面） | 轉檔中 | 不確定 | 取消 |
| 合併中（MP4） | 合併中 | 不確定 | 取消 |
| 完成 | ✓ 完成　1.6 MB（松綠）；略過的是 ✓ 檔案已存在，已略過 | 無 | 開啟資料夾、✕ |
| 失敗 | ⚠ 下載失敗：{錯誤 title}。{錯誤 hint}（磚紅 title、墨紫 hint，共一行，截斷時 `title` 屬性放全文） | 無 | 網路問題：重試、✕；未知錯誤：重試、✕，狀態列尾端另有文字連結「開啟記錄檔」；其他錯誤：只有 ✕ |
| 已取消 | 已取消 | 無 | 重新加入、✕ |

- MP4 的影像與聲音合成一條進度，只從 0 跑到 100 一次。
- 狀態列的數字用等寬數字，各段之間用全形空白隔開，不用中間點。
- 總大小未知時省略「/ 總大小」和「剩餘時間」，只顯示已下載大小與速度。
- ✕ 只出現在已結束的項目，名稱是「從佇列移除」。進行中的項目只有「取消」。
- 「清除已結束的」與 ✕ 只把項目從畫面移除，不刪檔案，所以不需要確認。移除後焦點移到「佇列（N）」標題。
- 焦點在某一列的按鈕上，那一列換了狀態（自己按的取消、重試、重新加入，或下載自己結束）：焦點留在同一列的第一顆按鈕（2026-11-18，4f 決定）。
- 「取消全部」（2026-11-17 決定加入）：先跳確認視窗（`cancelAll.title`、`cancelAll.body`；「繼續下載」是預設焦點，「取消全部」是磚紅按鈕）。確定後對每個還沒結束的項目叫一次 `cancel_task`，等待中的先、進行中的後，一起送出。做完焦點移到「佇列（N）」標題。不朗讀（使用者自己按的）。
- 開啟資料夾：選中檔案時不顯示任何東西；改開資料夾時 toast `toast.openedFolder`；什麼都沒開（或指令失敗）時 toast `toast.notFound`。
- 標題被截斷時：焦點在那一列的任何按鈕上，標題全文浮在那一列的文字欄上方（白底、邊框紫灰、最多三行、圖層 20），不改變列高。螢幕閱讀器從按鈕的 `aria-label` 聽得到全文。

## 朗讀（aria-live）

一個 `aria-live="polite"` 的區域，每則都帶標題。只唸看不到、使用者自己沒按的變化。

| 唸 | 鍵 |
|---|---|
| 按「加入佇列」後 | `live.added` |
| 自動加入 | `queue.autoAdded` |
| 完成（略過的另一句） | `live.done`、`live.skipped` |
| 失敗（帶錯誤 title） | `live.failed` |
| 剛進入重試中（次數增加不唸） | `live.retrying` |
| 移除、清除已結束的 | `live.removed` |

不唸：百分比、速度、剩餘時間；等待中 → 下載中、轉檔中、合併中；自己按的取消、重試、重新加入；查詢中 → 查到了（焦點會移到「加入佇列」）。

## 關閉確認

還有任務不是完成、失敗、已取消時按關閉，跳確認視窗（MASTER「確認視窗」）。按下時剛好全部結束了就直接關。

| 鍵 | 中文 | English |
|---|---|---|
| `close.title` | 還有 {{count}} 個下載沒完成，要關閉嗎？ | {{count}} download(s) haven't finished. Close anyway?（英文分單複數） |
| `close.body` | 關閉後，進行中與等待中的項目會停止，佇列不會保留，下次要重新加入。已完成的檔案不受影響。 | Items in progress or waiting will stop. The queue isn't kept, so you'll need to add them again. Finished files stay where they are. |
| `close.keep` | 繼續下載（預設焦點，Esc 也是它） | Keep downloading |
| `close.confirm` | 停止並關閉（磚紅底白字） | Stop and close |

## 空狀態

佇列沒有項目、也沒有預覽時，佇列的位置顯示：

```
                        ┌─────────┐
                        │ （插圖）│
                        └─────────┘
                     貼上網址開始下載
        複製 YouTube 影片或播放列表的網址，按 Ctrl+V 貼上。
```

- 插圖是三張疊在一起的封面方塊（淡梅紫、芥末黃、梅紫），用 CSS 畫，不用圖檔。靜態，不做動畫。
- 內容垂直置中、文字置中。不放按鈕，因為要做的動作就是貼上，網址列已經在上方。
- 有預覽但佇列是空的時候，佇列的位置只顯示一行「佇列是空的」。

## 文案

| 鍵 | 中文 | English |
|---|---|---|
| `url.label` | 影片或播放列表網址 | Video or playlist URL |
| `url.placeholder` | https://www.youtube.com/watch?v=… | https://www.youtube.com/watch?v=… |
| `url.lookUp` | 查詢 | Look up |
| `preview.loading` | 正在查詢影片資訊… | Looking up video info… |
| `preview.close` | 關閉預覽 | Close preview |
| `preview.note4k` | 4K 使用 VP9 編碼，部分播放器可能無法播放。 | 4K uses VP9, which some players can't play. |
| `queue.title` | 佇列（{{count}}） | Queue ({{count}})（有千分位） |
| `queue.cancelAll` | 取消全部 | Cancel all |
| `cancelAll.title` | 要取消 {{count}} 個還沒完成的項目嗎？ | {{count}} item(s) haven't finished. Cancel them all?（分單複數） |
| `cancelAll.body` | 進行中與等待中的項目會停止。已完成的檔案不受影響。取消的項目要逐一按「重新加入」才會再排。 | Items in progress or waiting will stop. Finished files stay where they are. Cancelled items have to be added again one by one. |
| `queue.clearFinished` | 清除已結束的 | Clear finished |
| `queue.emptyInline` | 佇列是空的 | The queue is empty |
| `queue.autoAdded` | 已將上一個項目加入佇列 | Added the previous item to the queue |
| `status.queued` | 等待中 | Waiting |
| `status.fetching` | 正在查詢影片資訊… | Looking up video info… |
| `status.starting` | 準備下載… | Starting download… |
| `status.downloading` | 下載中 {{percent}}% | Downloading {{percent}}% |
| `status.downloadingNoPercent` | 下載中 | Downloading |
| `status.progress` | {{done}} / {{total}} | {{done}} / {{total}} |
| `status.speed` | {{speed}}/s | {{speed}}/s |
| `status.eta` | 剩 {{time}} | {{time}} left |
| `status.retrying` | 連線中斷，重試中（第 {{n}} 次） | Connection lost, retrying (attempt {{n}}) |
| `status.converting` | 轉檔中 | Converting |
| `status.merging` | 合併中 | Merging |
| `status.done` | 完成 | Done |
| `status.failed` | 下載失敗：{{title}}。 | Download failed: {{title}}. |
| `status.cancelled` | 已取消 | Cancelled |
| `empty.title` | 貼上網址開始下載 | Paste a URL to start downloading |
| `empty.body` | 複製 YouTube 影片或播放列表的網址，按 Ctrl+V 貼上。 | Copy the URL of a YouTube video or playlist, then press Ctrl+V. |
| `preview.title` | 影片預覽 | Video preview |
| `toast.openedFolder` | 找不到檔案，已改開它原本所在的資料夾。 | Couldn't find the file, so its folder was opened instead. |
| `toast.notFound` | 找不到這個檔案和它所在的資料夾，可能已被移動或刪除。 | Couldn't find the file or its folder. It may have been moved or deleted. |
| `toast.notUrl` | 剪貼簿裡的不是網址。 | The clipboard doesn't contain a URL. |
| `crash.title` | 這個畫面出了問題 | Something went wrong on this screen |
| `crash.body` | 下載不受影響，仍在背景進行。重新載入畫面後會回到目前的佇列。 | Downloads aren't affected and keep running. Reload the screen to get back to your queue. |
| `crash.reload` | 重新載入畫面 | Reload screen |
| `live.added` | 已加入佇列：{{title}} | Added to the queue: {{title}} |
| `live.done` | 完成：{{title}} | Done: {{title}} |
| `live.skipped` | 檔案已存在，已略過：{{title}} | File already exists, skipped: {{title}} |
| `live.failed` | 下載失敗：{{title}}，{{reason}} | Download failed: {{title}}. {{reason}} |
| `live.retrying` | 連線中斷，正在重試：{{title}} | Connection lost, retrying: {{title}} |
| `live.removed` | 已從佇列移除 {{count}} 個項目 | Removed {{count}} from the queue |

按鈕（加入佇列、取消、重試、重新加入、從佇列移除、開啟資料夾、開啟記錄檔）與錯誤訊息用 MASTER 的共用文案。
