# 設定

> 功能型畫面。共用規則見 `../MASTER.md`；這裡寫的優先。

## 版面

```
│ 設定                                                         │
│                                                              │
│ 下載                                                         │
│   下載資料夾     D:\Music                          [變更…]   │
│   同時下載數     [ 1 | 2 | 3 | 4 | 5 ]                       │
│   檔名重複時     ( ) 略過   ( ) 覆蓋   (•) 自動改名          │
│                                                              │
│ 預設格式                                                     │
│   格式           [ MP3 | MP4 ]                               │
│   MP3 音質       [ 320 kbps ▾ ]                              │
│   MP4 畫質       [ 最高 1080p ▾ ]                            │
│   這些是貼上網址時預先選好的選項，會記住你上次用的。         │
│                                                              │
│ 介面                                                         │
│   語言           [ 跟隨系統 ▾ ]                              │
│                                                              │
│ 更新                                                         │
│   Media Downloader   0.1.0   有新版 0.2.0        [立即更新]  │
│   yt-dlp             2026.10.26                  [檢查更新]  │
│                                                              │
│ 關於                                                         │
│   …                                                          │
```

## 規則

- 內容寬度上限 640，靠左。整頁可以垂直捲動（這是唯一讓頁面捲動的畫面）。
- 五個區塊：下載、預設格式、介面、更新、關於。每個區塊是一個白底、圓角 10 的容器，區塊標題在容器上方（`<h2>`）。
- 每一列是「標籤在左（寬 160）、控制項在右」。最小視窗（網頁 707 寬）的英文介面也放得下，所以沒有「標籤在上」的窄版（`decisions/0016`）。例外是關於的元件清單：標籤在上、表格占整列寬。
- **改了就生效，沒有儲存按鈕。** 控制項先照使用者選的顯示；存不進去時彈回後端的值，不另外說明。
- 下載資料夾：顯示完整路徑，太長時從中間省略（保留磁碟與最後幾層）並用 `title` 屬性放完整路徑；鍵盤焦點在這一列時，完整路徑顯示在下方。「變更…」開啟系統的資料夾選擇視窗。
  - 選到不能寫入的資料夾：那一列下方一行磚紅訊息加警告圖示（`role="alert"`），到下一次按「變更…」時清掉。
  - 換成新資料夾、佇列還有沒完成的項目時 toast `settings.keptOldFolder`。按取消或選到同一個資料夾不說話。
- 同時下載數：並排的單選按鈕。範圍來自一個常數（1–5，`frontend/src/types.ts` 的 `CONCURRENT_CHOICES`），預設選 3。
- 檔名重複時：三個單選項。選「覆蓋」時下方顯示一行磚紅色的說明。
- 預設格式：跟預覽區塊「記住上次用的」是同一組值，兩邊改任何一邊都會同步。
- 語言：跟隨系統／繁體中文／English。語言名稱用該語言本身寫，不翻譯。
- 更新：
  - App 那一列只顯示目前版本。有新版時加上「有新版 x.y.z」與次要按鈕「立即更新」。按下才下載，不彈窗。導覽列的圓點一直顯示到沒有新版為止，看過設定頁也不消失（`decisions/0019`）。
    - 下載中：同一顆按鈕變「取消」；下方是確定進度條、「下載更新中 45%（50 MB / 110 MB）」與一行灰字說明下載完會關閉並安裝。
    - 核對中：不確定進度條與「正在核對檔案…」。
    - 核對完：佇列沒有沒完成的項目就直接安裝（「正在開啟安裝程式，App 即將關閉…」，按鈕 `aria-disabled`）；有就跳確認視窗（`appUpdate.confirmTitle`，「繼續下載」／「停止並更新」）。選「繼續下載」時按鈕變「立即安裝」，下方說明可以晚點再裝。
    - 失敗：磚紅一行加警告圖示說明原因（`network`、`checksumMismatch` 各有一句，其他用 `appUpdate.failedUnknown` 加「開啟記錄檔」），按鈕變「重試」，旁邊多一顆「前往下載」（開啟瀏覽器到發佈頁）。
    - 一直是同一顆按鈕，只換文字與動作，焦點留在它上面。
  - yt-dlp 那一列有「檢查更新」。按下後變成「檢查中…」並停用（`aria-disabled`，焦點留在按鈕上），下方一行「可能要二十秒左右」；結果顯示在那一列下方，到下一次檢查：「已是最新版」、「已更新到 x」、`network` 用 `settings.updateFailed`、其他用 `settings.updateFailedUnknown` 加「開啟記錄檔」。失敗時按鈕寫「重試」。
- 版本（App、yt-dlp、元件清單）第一次進這個畫面才讀（約 1.5 秒），讀取中用骨架佔位。
- 關於：App 名稱與版本、授權 MIT、使用的元件與各自的授權與版本（yt-dlp、FFmpeg、Deno、Noto Sans TC、Bricolage Grotesque）、「原始碼」、「開啟記錄檔資料夾」（兩顆次要按鈕）。

## 文案

| 鍵 | 中文 | English |
|---|---|---|
| `settings.title` | 設定 | Settings |
| `settings.download` | 下載 | Downloads |
| `settings.folder` | 下載資料夾 | Download folder |
| `settings.changeFolder` | 變更… | Change… |
| `settings.concurrent` | 同時下載數 | Simultaneous downloads |
| `settings.duplicate` | 檔名重複時 | If the file already exists |
| `settings.duplicateSkip` | 略過 | Skip |
| `settings.duplicateOverwrite` | 覆蓋 | Overwrite |
| `settings.duplicateRename` | 自動改名 | Rename automatically |
| `settings.overwriteWarning` | 同名的舊檔案會被取代，無法復原。 | The existing file will be replaced and can't be recovered. |
| `settings.defaults` | 預設格式 | Default format |
| `settings.mp3Quality` | MP3 音質 | MP3 quality |
| `settings.mp4Quality` | MP4 畫質 | MP4 quality |
| `settings.defaultsHint` | 這些是貼上網址時預先選好的選項，會記住你上次用的。 | These are preselected when you paste a URL, and remember what you last used. |
| `settings.interface` | 介面 | Interface |
| `settings.language` | 語言 | Language |
| `settings.languageSystem` | 跟隨系統 | Match system |
| `settings.updates` | 更新 | Updates |
| `settings.newVersion` | 有新版 {{version}} | Version {{version}} is available |
| `settings.getUpdate` | 前往下載 | Get the update |
| `settings.checkUpdate` | 檢查更新 | Check for updates |
| `settings.checking` | 檢查中… | Checking… |
| `settings.upToDate` | 已是最新版 | Up to date |
| `settings.updatedTo` | 已更新到 {{version}} | Updated to {{version}} |
| `settings.updateFailed` | 無法檢查更新，請檢查網路連線後重試。 | Couldn't check for updates. Check your internet connection, then retry. |
| `settings.about` | 關於 | About |
| `settings.license` | 授權 | License |
| `settings.components` | 使用的元件 | Third-party components |
| `settings.sourceCode` | 原始碼 | Source code |
| `settings.openLogFolder` | 開啟記錄檔資料夾 | Open log folder |
| `settings.languageZhTW` | 繁體中文 | 繁體中文 |
| `settings.languageEn` | English | English |
| `settings.checkingSlow` | 可能要二十秒左右。 | This can take about 20 seconds. |
| `settings.updateFailedUnknown` | 無法更新 yt-dlp。可以重試；如果還是不行，記錄檔裡有詳細資訊。 | Couldn't update yt-dlp. You can retry. The log file has details. |
| `settings.appLicense` | {{version}}，MIT 授權 | {{version}}, MIT License |
| `settings.componentName` | 名稱 | Name |
| `settings.version` | 版本 | Version |
| `settings.aboutFailed` | 無法讀取版本資訊。 | Couldn't read the version information. |
| `settings.folderNotWritable` | 這個資料夾無法寫入，請選其他資料夾。 | This folder can't be written to. Choose another folder. |
| `settings.keptOldFolder` | 已換成新的下載資料夾。佇列裡還沒完成的 {{count, number}} 個項目仍會存到原本的資料夾。 | Download folder changed. The {{count, number}} unfinished items in the queue still go to the old folder.（單數另有一句） |

最後十個是 4e 實作時加的（`decisions/0016`）。重試、開啟記錄檔用 MASTER 的共用文案。`settings.getUpdate`（前往下載）5b 起只在 App 更新失敗時出現。

App 更新的文案在語言檔的 `appUpdate.*`（5b，`decisions/0019`）：`updateNow` 立即更新、`installNow` 立即安裝、`downloading`、`downloadingNoTotal`、`closesAfter`、`verifying`、`ready`、`installing`、`failedNetwork`、`failedChecksum`、`failedUnknown`、`confirmTitle`、`confirmBody`、`confirm` 停止並更新。確認視窗的「繼續下載」沿用 `close.keep`。
