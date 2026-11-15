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
│   Media Downloader   0.1.0   有新版 0.2.0        [前往下載]  │
│   yt-dlp             2026.10.26                  [檢查更新]  │
│                                                              │
│ 關於                                                         │
│   …                                                          │
```

## 規則

- 內容寬度上限 640，靠左。整頁可以垂直捲動（這是唯一讓頁面捲動的畫面）。
- 五個區塊：下載、預設格式、介面、更新、關於。每個區塊是一個白底、圓角 10 的容器，區塊標題在容器上方（`<h2>`）。
- 每一列是「標籤在左（寬 160）、控制項在右」。視窗窄到放不下時改成標籤在上。
- **改了就生效，沒有儲存按鈕。**
- 下載資料夾：顯示完整路徑，太長時從中間省略並用 `title` 屬性放完整路徑。「變更…」開啟系統的資料夾選擇視窗。
- 同時下載數：並排的單選按鈕。範圍來自一個常數（1–5，`frontend/src/types.ts` 的 `CONCURRENT_CHOICES`），預設選 3。
- 檔名重複時：三個單選項。選「覆蓋」時下方顯示一行磚紅色的說明。
- 預設格式：跟預覽區塊「記住上次用的」是同一組值，兩邊改任何一邊都會同步。
- 語言：跟隨系統／繁體中文／English。語言名稱用該語言本身寫，不翻譯。
- 更新：
  - App 那一列只顯示目前版本。有新版時加上「有新版 x.y.z」與次要按鈕「前往下載」（開啟瀏覽器到發佈頁）。不自動下載、不彈窗。
  - yt-dlp 那一列有「檢查更新」。按下後變成「檢查中…」並停用；結果顯示在同一列：「已是最新版」、「已更新到 x」或錯誤訊息加「重試」。
- 關於：App 名稱與版本、授權 MIT、使用的元件與各自的授權（yt-dlp、FFmpeg、Deno、Noto Sans TC、Bricolage Grotesque）、「原始碼」連結、「開啟記錄檔資料夾」。

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

重試用 MASTER 的共用文案。
