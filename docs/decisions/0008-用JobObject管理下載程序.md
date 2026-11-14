<!--
這個資料夾是什麼：架構決策紀錄（ADR），一個重大決定一份（NNNN-標題.md，編號遞增）。
推上 GitHub：可以。公開前改寫成英文。
-->

# 0008. 用 Windows Job Object 管理下載程序

- 日期：2026-11-14
- 狀態：已採用

## 背景

`yt-dlp.exe` 是兩層程序，還會自己啟動 Deno 和 FFmpeg。技術驗證（第 6 項）確認取消時要結束整棵程序樹，當時用的是 `taskkill /T /F`，並留下一個沒測的問題：App 本身被強制結束時，下載程序會不會留在背景。

階段 3b 實測（`docs/技術驗證.md` 第 16 項）：

- 沒有特別處理時，App 在 FFmpeg 轉檔中被強制結束，`yt-dlp.exe` 與 `ffmpeg.exe` 會留在背景繼續轉，直到轉完才結束。
- 把程序放進設定了「控制代碼關閉時結束所有程序」的 Job Object，App 被強制結束後 1 秒內全部結束。
- 取消：`taskkill /T /F` 約 0.3 秒，結束 Job 約 0.005 秒。

## 決定

每個由引擎啟動的外部程式都放進自己的 Job Object（`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`）。

- 程式以暫停狀態啟動（`CREATE_SUSPENDED`），放進 Job 之後才放行，所以它啟動的任何子程序一定在 Job 裡。
- 取消就是結束整個 Job（`TerminateJobObject`）。不再使用 `taskkill`。
- Job 的控制代碼只有 App 持有。App 不論怎麼結束，Windows 都會關掉它，Job 裡的程序跟著結束。
- 實作在 `backend/app/infrastructure/engines/ytdlp/process.py`，用標準函式庫的 `ctypes`，沒有新增套件。

## 理由

- 只有這個做法能處理「App 被強制結束」。
- 取消不必另外啟動一個程式，也不會漏掉取消當下才啟動的子程序。
- 查資訊、查版本、更新也走同一條路，逾時的時候同樣結束整個 Job。

## 考慮過的其他做法

- `taskkill /PID <pid> /T /F`：只要幾行，但 App 被強制結束時沒有人去執行它。
- 不暫停、啟動後立刻放進 Job：不需要 `NtResumeProcess`，但程式在被放進 Job 之前有極短的時間可以先啟動子程序。
- 整個 App 放進一個 Job：WebView2 的程序也會在裡面，取消單一任務時也沒辦法只結束那一個。

## 後果

- 放行暫停的程序用的是 `NtResumeProcess`，微軟沒有把它寫進正式文件（psutil 也用它）。哪天不能用了，退路是上面第二個做法。
- 這段程式只能在 Windows 上執行；測試（CI 跑在 windows-latest）用 Python 子程序驗證「結束 Job」與「關掉控制代碼」都會帶走整棵樹。
- App 被強制結束後，任務的暫存資料夾還在，要靠下次啟動時清理（`YtDlpEngine.remove_stale_temp`，由 3c 的啟動流程呼叫）。
- 還沒驗證：打包後的 App；App 本身已經在別的 Job 裡的情況（Windows 8 以上支援巢狀 Job）。
