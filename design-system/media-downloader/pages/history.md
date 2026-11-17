# 歷史紀錄

> 功能型畫面。共用規則見 `../MASTER.md`；這裡寫的優先。

## 版面

```
│ 歷史紀錄                                           [清空紀錄]│
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ┌────┐ （標題）                                 MP3      │ │
│ │ │封面│ 2026年11月13日 下午2:20　9.2 MB　✓已加入佇列     │ │
│ │ └────┘              [重新下載] [開啟資料夾]          🗑   │ │
│ ├──────────────────────────────────────────────────────────┤ │
```

## 規則

- 用跟佇列相同的列（MASTER 第 6 節），列高一樣是 72。差別：狀態列顯示檔案大小與完成時間，第三行放按鈕而不是進度條。
- 最新的在最上面。超過 100 列時用虛擬清單。
- 這個畫面例外：每列有兩顆文字按鈕（重新下載、開啟資料夾）加一個圖示按鈕。
- 「重新下載」用當時的格式與音質／畫質直接加入佇列，不經過預覽；加入後停在這個畫面，在 `aria-live` 區域宣告「已加入佇列」。
- 垃圾桶圖示是「刪除這筆紀錄」：只刪紀錄、不刪檔案，不需要確認。
- 「清空紀錄」是危險按鈕，放在標題列右側，跟每列的按鈕分開。沒有紀錄時不顯示。
- 「清空紀錄」要先確認。確認視窗的規則見 MASTER 第 6 節；危險按鈕的文字跟觸發它的按鈕相同。
- 日期時間依介面語言的格式顯示（`Intl.DateTimeFormat`）。
- 沒有搜尋（第一版不做）。

4d 定的（依據見 `docs/decisions/0015`）：

- 狀態列：完成時間在前，檔案大小與「已加入佇列」接在後面；放不下時換到第二行（列沒有進度條，那一行空著）。最小視窗的英文介面一定會換行。
- 時間：`Intl.DateTimeFormat(語言, { dateStyle: 'medium', timeStyle: 'short' })`。
- 第一次進畫面時載入一次；載入中不顯示清單與「清空紀錄」；載入失敗顯示 `history.loadFailed` 與「重試」。
- 按過「重新下載」：那一列的狀態列加綠色勾與 `history.addedToQueue`，按鈕照樣能按；朗讀 `live.added`（帶標題）。紀錄不在了：toast `history.gone` 並拿掉那一列；失敗：toast `history.notAdded`。
- 刪除這筆紀錄：焦點移到取代它位置那一列的刪除按鈕，最後一列就移到上一列，全部刪光移到「前往下載」。朗讀 `history.deleted`。
- 清空後焦點移到「前往下載」。
- 「清空紀錄」用危險的外框按鈕（白底、磚紅框與字，滑過淡磚紅底）。

## 空狀態

```
                      還沒有下載紀錄
              下載完成的檔案會列在這裡。
                      [前往下載]
```

「前往下載」是次要按鈕，切到主畫面並把焦點放在網址輸入框。

## 文案

| 鍵 | 中文 | English |
|---|---|---|
| `history.title` | 歷史紀錄 | History |
| `history.downloadAgain` | 重新下載 | Download again |
| `history.addedToQueue` | 已加入佇列 | Queued |
| `history.deleteEntry` | 刪除這筆紀錄 | Delete this entry |
| `history.clear` | 清空紀錄 | Clear history |
| `history.confirmTitle` | 清空全部 {{count, number}} 筆紀錄？ | Clear all {{count, number}} entries?（1 筆：Clear 1 entry?） |
| `history.confirmBody` | 已下載的檔案不會被刪除。這個動作無法復原。 | Downloaded files won't be deleted. This can't be undone. |
| `history.emptyTitle` | 還沒有下載紀錄 | No downloads yet |
| `history.emptyBody` | 下載完成的檔案會列在這裡。 | Files you finish downloading will be listed here. |
| `history.goToDownloads` | 前往下載 | Go to Downloads |

| `history.deleted` | 已刪除這筆紀錄：{{title}} | Deleted the entry: {{title}} |
| `history.gone` | 這筆紀錄已經不在了。 | This entry no longer exists. |
| `history.notAdded` | 沒有加入佇列，請再試一次。 | Couldn't add it to the queue. Try again. |
| `history.loadFailed` | 無法讀取歷史紀錄。 | Couldn't read the history. |

開啟資料夾、取消、重試用 MASTER 的共用文案；開啟資料夾的 toast 跟佇列相同。
