<!--
What this file is: the change log of media-downloader, one section per version (Keep a Changelog format).
Changes users can see go into [Unreleased]; on release it becomes [x.y.z] - YYYY-MM-DD.
Release notes are taken from here.
Published on GitHub: yes.
-->

# Changelog

All notable changes to this project are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.1] - 2026-11-27

### Fixed

- The 1.0.0 release was published without its installer. 1.0.1 is the first release you can install.
- The log also masks the short (8.3) form of your user folder, such as `C:\Users\SOMEON~1`, which Windows uses in some paths.

## [1.0.0] - 2026-11-27

The first public version of Media Downloader, a Windows app that downloads music (MP3) and video (MP4) from YouTube.

### Added

- **Downloading**
  - Paste a YouTube URL anywhere in the window with Ctrl+V, or type it into the URL box. A preview shows the thumbnail, title, channel and length.
  - MP3 at 128, 192 or 320 kbps, with the cover embedded and cropped to a square.
  - MP4 in the qualities that video actually has, with an estimated file size. 4K is VP9 inside MP4, which some players can't play.
  - Format and quality remember what you used last.
  - File names are the video title. When a file already exists: skip, overwrite or rename automatically (`Song (1).mp3`).
  - Downloads finish in a hidden temporary folder, so the download folder never holds half-finished files.
- **Queue**
  - Queue many URLs at once, with 1–5 simultaneous downloads (3 by default).
  - Each item shows its own progress and stage: waiting, downloading (with a real percentage), converting, merging.
  - Cancel, retry, add again, remove, clear finished, cancel all (after a confirmation). Open the folder of a finished file.
  - Errors say what happened and what to do next: private, age-restricted, members-only, region-blocked, removed, live stream, no connection. Unknown errors have "Open log file".
  - A download refused by YouTube (HTTP 403) is tried once more by itself.
  - Long queues stay fast: only the visible rows are drawn.
  - Closing the window with unfinished downloads asks first.
- **Playlists and channels**
  - Paste a playlist or channel URL to list every video and tick the ones to download. Private or deleted videos are shown as unavailable.
  - The whole selection uses one format; MP4 quality is an upper limit ("Up to 1080p").
  - Works with lists of thousands of videos, and with the keyboard alone.
- **History**
  - Every finished download is listed with its thumbnail, time and size. Download again with the same format, open its folder, delete an entry or clear all. Downloaded files are never deleted.
- **Settings**
  - Download folder, simultaneous downloads, duplicate files, default format and quality, and language (match system, Traditional Chinese, English). Changes apply at once.
  - About: version, licenses of the main third-party components, source code link, open log folder.
- **Updates**
  - When a new version is out, a dot appears next to Settings, and "Update now" downloads the installer, checks its SHA-256, installs it and reopens the app. Nothing happens until you choose it.
  - yt-dlp updates itself when the app starts (at most once a day), and can be updated by hand in Settings.
- **Installer**
  - Installs for the current user only, without administrator rights. Start menu shortcut; the installer follows the system language (Traditional Chinese, English).
  - Updating or reinstalling never replaces a newer yt-dlp with an older one.
  - Uninstalling asks whether to delete your settings, history and log files (kept by default).
  - Warns when WebView2 is missing and links to Microsoft's download.
  - Includes the license texts of every bundled third-party component and how to get FFmpeg's source.
  - Each release has a `.sha256` file that `sha256sum -c` (Linux, macOS) and PowerShell can check.
- Keyboard and screen reader support throughout: visible focus, announced status changes (not percentages), the full title of a cut-off row on focus.
- The app's own network requests verify certificates with Windows, like a browser.
- The log masks your user folder in paths.

[Unreleased]: https://github.com/kdwjzh/media-downloader/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/kdwjzh/media-downloader/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/kdwjzh/media-downloader/releases/tag/v1.0.0
