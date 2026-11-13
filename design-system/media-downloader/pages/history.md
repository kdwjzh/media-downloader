# 歷史紀錄

> 功能型畫面。共用規則見 `../MASTER.md`；這裡寫的優先。

## 版面

```
│ 歷史紀錄                                           [清空紀錄]│
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ┌────┐ （標題）                                 MP3      │ │
│ │ │封面│ 9.2 MB　2026/11/13 14:20                          │ │
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
| `history.addedToQueue` | 已加入佇列 | Added to queue |
| `history.deleteEntry` | 刪除這筆紀錄 | Delete this entry |
| `history.clear` | 清空紀錄 | Clear history |
| `history.confirmTitle` | 清空全部 {{count}} 筆紀錄？ | Clear all {{count}} entries? |
| `history.confirmBody` | 已下載的檔案不會被刪除。這個動作無法復原。 | Downloaded files won't be deleted. This can't be undone. |
| `history.emptyTitle` | 還沒有下載紀錄 | No downloads yet |
| `history.emptyBody` | 下載完成的檔案會列在這裡。 | Files you finish downloading will be listed here. |
| `history.goToDownloads` | 前往下載 | Go to Downloads |

開啟資料夾、取消用 MASTER 的共用文案。
