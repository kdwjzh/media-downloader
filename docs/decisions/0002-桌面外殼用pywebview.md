<!--
這個資料夾是什麼：架構決策紀錄（ADR），一個重大決定一份（NNNN-標題.md，編號遞增）。
推上 GitHub：可以。維持中文（只有 README.md、CHANGELOG、CLAUDE.md 是英文，見 0021）。
-->

# 0002. 桌面外殼用 pywebview

- 日期：2026-11-11
- 狀態：已採用

## 背景

決定用網頁技術做介面後（見 0001），需要一個把網頁包成桌面視窗、並讓介面能呼叫 Python 的外殼。

## 決定

用 pywebview。Windows 上使用系統的 WebView2。

## 理由

- 只有一個 Python 程序，介面可以直接呼叫 Python 函式，出問題時好找。
- 專案只有兩種語言（Python、TypeScript）。
- 可維護性是這次重寫的首要要求。

## 考慮過的其他做法

- Tauri + Python sidecar：內建安裝檔製作與更新機制，但多一種語言（Rust），介面要經過 Rust 再轉給另一個 Python 程序，要自己定通訊格式。另有回報指出 PyInstaller 做的 sidecar 在重新安裝時可能沒被換成新版（tauri-apps/tauri#15134）。
- Electron：體積大，同樣需要另外帶一個 Python 程序。

## 後果

- 安裝檔製作與 App 更新檢查要自己做。
- 介面只透過 `frontend/src/api/` 呼叫橋接層；日後要換外殼，只需改橋接層與這個資料夾。
