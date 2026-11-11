<!--
這個檔案是什麼：media-downloader 的使用說明：是什麼、怎麼安裝、怎麼用、怎麼更新。
功能或使用方式有變就更新；README.md 和 README.zh-TW.md 要一起改。
推上 GitHub：可以。公開前 README.md 改寫成英文。
-->

[English](README.md) | [繁體中文](README.zh-TW.md)

# media-downloader

以抓音樂為主、影片為輔的 Windows 桌面下載器，用下載佇列一次處理多首歌和整個播放列表。

## 安裝

## 使用方式

## 更新

## 常見問題

## 開發

需要：Python 3.12 以上、[uv](https://docs.astral.sh/uv/)、Node.js（LTS）。

第一次先安裝依賴：

```bash
cd backend && uv sync && uv run pre-commit install
```

```bash
cd frontend && npm install
```

啟動開發環境（同時啟動介面的開發伺服器與桌面視窗；關掉視窗就會一起結束）：

```bash
python scripts/dev.py
```

送出前跑一鍵檢查（後端與介面的 lint、型別檢查、測試）：

```bash
python scripts/check.py
```

## 授權

[MIT](LICENSE)
