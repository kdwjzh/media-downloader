<!--
這個資料夾是什麼：架構決策紀錄（ADR），一個重大決定一份（NNNN-標題.md，編號遞增）。
推上 GitHub：可以。維持中文（只有 README.md、CHANGELOG、CLAUDE.md 是英文，見 0021）。
-->

# 0022. 用 workflow 發佈 Release，不用網頁的 Publish

- 日期：2026-11-27
- 狀態：已採用（補充 `0020` 第 1 項：draft 仍由推 tag 產生，「作者手動發佈」改成手動觸發 workflow）

## 背景

v1.0.0 的 draft 由 `release.yml` 建立，發佈前確認過上面剛好兩個檔（安裝檔與 `.sha256`），檢查碼也在 release job 核對過。
發佈時開了 `releases/edit/v1.0.0`：貼上說明、按「Publish release」、在不可變 Release 的確認框再按一次。發佈後 v1.0.0 只剩 Source code 與 Release attestation，兩個檔都不見了（API 的 assets 是空的，下載網址 404）。
repo 開了不可變 Release（5e 的決定）：已發佈的版本不能再加檔案，刪掉之後 tag 名稱也不能再用。所以 v1.0.0 留著，說明開頭註明沒有安裝檔，改由 1.0.1 當第一個能用的版本。

原因（1.0.1 的 draft 出來時查到）：draft 還沒有正式掛上 tag，它的網址是 `releases/tag/untagged-…`，編輯頁是 `releases/edit/untagged-…`。用 tag 名稱組的 `releases/edit/v1.0.0` 不是那份 draft，在那裡按 Publish 是替同一個 tag **另建一個沒有檔案的 Release**；原本的 draft 連同兩個檔都還在。draft 真正的編輯頁有列出兩個檔。網頁本身沒有弄丟檔案，是開錯了頁面。

## 決定

1. `release.yml` 手動觸發時多一個輸入 `publish`：填 tag（`v1.2.3`）就只跑 `publish` job，不打包。
2. `publish` job 先確認那個 Release 是 draft、上面剛好是 `MediaDownloader-Setup-<版本>.exe` 與同名 `.sha256`，再用 `gh release edit <tag> --draft=false` 發佈，發佈後再看一次檔案沒變。不符合就失敗，不發佈。
3. 這個 job 是唯一的發佈方式，不用網頁編輯頁的「Publish release」：要找對 draft 的頁面（`edit/untagged-…`），開錯了也看不出來。
4. 說明在發佈**之後**才到網頁上貼（不可變 Release 發佈後只能改標題與說明，檔案不會再被動到）。
5. tag 從 `inputs` 經環境變數傳進 shell，先檢查格式，不直接寫進指令。

## 理由

- API 只改 draft 這個欄位，不會送出附件清單；job 前後都檢查檔案，就算行為變了也會在發佈前停下。
- 用 `GITHUB_TOKEN`，作者的電腦不需要 gh 或 token。
- 第一次實跑：v1.0.1（run 45963130799）發佈成功，`gh` 找得到 draft，前後兩次檢查都是那兩個檔。
- 說明晚一點出現沒有關係；檔案一旦在不可變 Release 上缺了就救不回來。

## 考慮過的其他做法

- 繼續用網頁發佈，從 Releases 列表點 draft 的編輯鈕：做得到，但開錯頁面時畫面看起來一樣，只有發佈後才發現；job 按 tag 找、前後檢查檔案。
- 推 tag 直接發佈、不經過 draft：發佈前就沒有機會核對。
- release job 從 CHANGELOG 取說明寫進 draft：可以少貼一次，但要從 Markdown 切出一段；之後要做再決定。

## 代價

- 發佈多一步：到 Actions 手動觸發並填 tag。
- 發佈後到貼上說明之前，說明只有 tag 的訊息。
- v1.0.0 永遠沒有安裝檔。
