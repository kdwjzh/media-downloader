<!--
這個資料夾是什麼：架構決策紀錄（ADR），一個重大決定一份（NNNN-標題.md，編號遞增）。
推上 GitHub：可以。維持中文（只有 README.md、CHANGELOG、CLAUDE.md 是英文，見 0021）。
-->

# 0001. Python 後端加 React 介面

- 日期：2026-11-11
- 狀態：已採用

## 背景

舊專案用 Python + CustomTkinter。這次重寫有兩個目的：把下載器做得好維護，以及拿它練習 UI 設計流程（ui-ux-pro-max 與 frontend-design 兩個 skill）。ui-ux-pro-max 支援的框架清單裡沒有 CustomTkinter，frontend-design 也以網頁技術為主。作者的下一個專案同樣是桌面程式，希望這次的做法能沿用。

## 決定

後端用 Python，介面用 React + TypeScript + Vite + Tailwind，包成桌面視窗。

## 理由

- 下載邏輯留在作者熟悉的 Python。
- 介面用網頁技術，兩個 UI skill 才能完整發揮，練到的流程可以帶到下一個專案。
- 介面與後端天生分成兩塊，分層界線清楚。

## 考慮過的其他做法

- PySide6（Qt）：全程 Python、打包成熟，但不在 ui-ux-pro-max 的框架清單內，UI 練習效果打折。
- C# + WinUI／WPF：最像 Windows 原生程式，但要換語言，yt-dlp 只能當外部程式呼叫。
- 繼續用 CustomTkinter：視覺自由度低，兩個 skill 都使不上力。
