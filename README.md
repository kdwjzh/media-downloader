<!--
What this file is: the user guide of media-downloader: what it is, how to install, use and update it.
Update it when features or usage change; README.md and README.zh-TW.md match section by section, change them together.
Published on GitHub: yes.
-->

[English](README.md) | [繁體中文](README.zh-TW.md)

# Media Downloader

A Windows desktop app for downloading music (MP3) and video (MP4) from YouTube. Paste many URLs or a whole playlist, and the download queue handles them one after another.

- Queue: many downloads at once, each with its own progress; cancel, retry, add again.
- Playlists and channels: list every video and tick the ones you want.
- MP3 at 128 / 192 / 320 kbps with the cover embedded; MP4 in the qualities the video actually has.
- History of finished downloads; interface in English and Traditional Chinese.

## Requirements

- Windows 10 or 11, 64-bit.
- Microsoft Edge WebView2 Runtime. Windows 11 has it; on an older Windows 10 the installer tells you if it's missing and where to get it.
- Only YouTube is supported and tested.

## Installing

1. Open the [Releases](https://github.com/kdwjzh/media-downloader/releases) page and download two files from the latest version:
   - `MediaDownloader-Setup-<version>.exe` (the installer)
   - `MediaDownloader-Setup-<version>.exe.sha256` (its checksum)
2. Check the installer wasn't damaged or changed (optional, recommended). In PowerShell, in the folder you downloaded to:

   ```powershell
   (Get-FileHash .\MediaDownloader-Setup-<version>.exe -Algorithm SHA256).Hash
   Get-Content .\MediaDownloader-Setup-<version>.exe.sha256
   ```

   The two long strings must be the same (the first is in capitals, which doesn't matter). On Linux or macOS: `sha256sum -c MediaDownloader-Setup-<version>.exe.sha256` (macOS: `shasum -a 256 -c …`) must print `OK`.
3. Run the installer. The installer isn't code-signed, so Windows may show a blue **Windows protected your PC** window. Choose **More info**, check that the app is `MediaDownloader-Setup-<version>.exe`, then choose **Run anyway**.
   <!-- 5d: confirm the exact wording against the Windows Sandbox screenshots. -->
4. Follow the installer. It installs for your user only and doesn't need administrator rights:
   - The app: `%LOCALAPPDATA%\Programs\Media Downloader`
   - yt-dlp, FFmpeg and Deno: `%LOCALAPPDATA%\media-downloader\bin`
5. Start **Media Downloader** from the Start menu.

## Using it

The navigation on the left has three screens: Downloads, History and Settings. Switching screens keeps the preview, ticked items and scroll position.

### Pasting a URL and the preview

1. Copy the URL of a YouTube video and press Ctrl+V anywhere in the window. You can also paste it into "Video or playlist URL" and choose "Look up" or press Enter.
2. The preview shows the thumbnail, title, channel and length. Choose the format (MP3 or MP4) and the audio or video quality:
   - MP3: 128, 192 or 320 kbps. The thumbnail is square, and the file gets the cover embedded.
   - MP4: only the qualities this video actually has. 4K uses VP9, which some players can't play.
   - The estimated size is shown below; "Size unknown" when there is no estimate.
3. Choose "Add to queue".

Format and quality remember what you used last. If you paste another URL while a preview hasn't been added yet: one already looked up is added with the format chosen at that moment, one still being looked up is added too and starts when found, and one that failed is simply replaced.

### Playlists

Paste the URL of a playlist or of a channel's videos page to get a list to tick:

- Everything is ticked at first; use "Select all" or tick rows one by one. Private or deleted videos show "Unavailable" and can't be ticked.
- The whole selection uses one format and quality. For MP4 the quality is an upper limit (e.g. "Up to 1080p"): each video gets the highest quality it has, up to that limit.
- Choose "Add N to queue". "Cancel" or ✕ goes back to the main screen without touching the queue.
- Keyboard only: Tab into the list, arrow keys to move, Space to tick.
- Long lists take a while to look up (over ten seconds for thousands of videos); the wait shows how many seconds have passed.

### Queue

- Each item has its own progress and current stage (waiting, downloading, converting, merging). Change the number of simultaneous downloads in Settings.
- Items in progress or waiting can be cancelled; cancelled ones can be added again; ones that failed because of the network or an unknown error can be retried.
- "Cancel all" asks first. Cancelled items have to be added again one by one.
- A finished item can "Open folder", which selects the file in File Explorer.
- ✕ and "Clear finished" only take items off the queue; they never delete files.
- A failure says why and what to do next (e.g. private video, region restriction, no connection). Unknown errors have "Open log file", where the details are.
- Closing the window with unfinished items asks first; once you confirm, items in progress or waiting stop and the queue isn't kept.

### History

Every finished download is listed here, newest first:

- "Download again" adds it to the queue with the same format and quality.
- "Open folder" selects the file in File Explorer; if the file is gone, its original folder opens instead.
- The trash icon deletes that entry; "Clear history" asks first. Both delete only entries, never files.

### Settings

Changes apply at once; there is no Save button.

- Download folder: choose "Change…". Unfinished items already in the queue still go to the old folder.
- Simultaneous downloads: 1 to 5, 3 by default.
- If the file already exists: skip, overwrite (the old file is replaced and can't be recovered) or rename automatically.
- Default format: MP3 quality and MP4 quality, the same values the preview remembers.
- Language: match system, Traditional Chinese, English.
- Updates: see [Updating](#updating).
- About: version, licenses, third-party components, "Source code" and "Open log folder".

## Updating

- **Media Downloader**: when a new version is out, a dot appears next to "Settings" in the navigation. In Settings choose "Update now": the app downloads the new installer, checks its SHA-256, closes, installs it and opens again. Your settings and history are kept. If downloads are still running, it asks first. Nothing is downloaded until you choose it.
- **yt-dlp** (what actually downloads from YouTube) updates itself in the background when the app starts, at most once a day. You can also choose "Check for updates" next to yt-dlp in Settings (it can take about 20 seconds). When downloads start failing after YouTube changes something, this is usually the fix.

## Uninstalling

Open Windows **Settings → Apps → Installed apps** (Windows 10: **Apps & features**), find **Media Downloader** and choose Uninstall. The uninstaller asks whether to also delete your settings, history and log files; choose No to keep them for a later reinstall. yt-dlp, FFmpeg and Deno are always removed. Downloaded files are never touched.

## Where your data is

| What | Where |
| --- | --- |
| Settings and history | `%APPDATA%\media-downloader` |
| Log files | `%LOCALAPPDATA%\media-downloader\logs` |
| yt-dlp, FFmpeg, Deno | `%LOCALAPPDATA%\media-downloader\bin` |
| Downloaded files | Your Downloads folder, or the folder chosen in Settings |

The log files don't record video titles, and your user folder is masked in paths.

## FAQ

**What do the error messages mean?**

| Message | Meaning |
| --- | --- |
| This video is private | Only people the uploader allows can watch it. |
| This video is age-restricted / for members only | These need a signed-in account, which isn't supported. |
| This video isn't available in your region | The uploader limited where it can be watched. |
| Video not found / Playlist not found | Removed, private, or the URL is wrong. |
| Live streams aren't supported | Wait until the stream ends and the video is published. |
| This site isn't supported | Only YouTube URLs are accepted. |
| Can't connect | Check your internet connection, then Retry. |
| Something unexpected went wrong | Retry; if it keeps failing, update yt-dlp in Settings. "Open log file" shows the details. |

**Can it download age-restricted or members-only videos?** No. They need signing in with your account, which this app doesn't do.

**Does it work with other sites?** Only YouTube is supported and tested.

**Why does Windows warn me when I run the installer?** The installer isn't code-signed (certificates are paid yearly). See step 3 of [Installing](#installing), and check the SHA-256 if you want to be sure the file is the one released here.

**A 4K video won't play.** 4K on YouTube is VP9, which some players can't play. Try a player such as VLC, or choose 1080p.

## Terms of use

This app is a tool. You are responsible for making sure that what you download, and how you use it, is legal where you live and allowed by the terms of the site you download from. Only download content you have the right to download.

## License and third-party components

Media Downloader is released under the [MIT License](LICENSE).

The installer includes these components, each under its own license:

| Component | License | Notes |
| --- | --- | --- |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | Downloads from YouTube |
| [FFmpeg](https://ffmpeg.org/) | GPL-3.0-or-later | Converts and merges; shipped unchanged from [yt-dlp/FFmpeg-Builds](https://github.com/yt-dlp/FFmpeg-Builds/releases/tag/autobuild-2026-10-31-18-18). Source: [FFmpeg at this build's commit](https://github.com/FFmpeg/FFmpeg/tree/6d1bfd760916ab52814b950692d1c1635d29f3c7) and [the build scripts](https://github.com/yt-dlp/FFmpeg-Builds/tree/5ece62897c650b863c1ddda7b6964845344aef2d) |
| [Deno](https://github.com/denoland/deno) | MIT | JavaScript runtime that yt-dlp needs |
| [Noto Sans TC](https://fonts.google.com/noto/specimen/Noto+Sans+TC) | OFL-1.1 | Font |
| [Bricolage Grotesque](https://github.com/ateliertriay/bricolage) | OFL-1.1 | Font |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause | The app window (includes Microsoft's WebView2 SDK) |
| [truststore](https://github.com/sethmlarson/truststore) | MIT | Lets Windows verify certificates |

The app also contains the Python runtime and other Python packages, and React and other npm packages. The full license texts of everything above and of those are in the `licenses` folder where the app is installed (`%LOCALAPPDATA%\Programs\Media Downloader\licenses`).

## Documentation language

This README, [CHANGELOG.md](CHANGELOG.md) and [CLAUDE.md](CLAUDE.md) are in English. The design documents in [`docs/`](docs/) and [`design-system/`](design-system/) are in Traditional Chinese.

## Development

Needs Python 3.12 or later, [uv](https://docs.astral.sh/uv/) and Node.js (LTS).

Install the dependencies the first time:

```bash
cd backend && uv sync && uv run pre-commit install
```

```bash
cd frontend && npm install
```

Fetch the external programs (yt-dlp, FFmpeg, Deno) into `bin/`, checking the SHA-256 their sources publish; `bin/` isn't in git:

```bash
python scripts/fetch_binaries.py
```

Start the development environment (the UI dev server and the desktop window; closing the window stops both):

```bash
python scripts/dev.py
```

Run the one-step check before sending changes (lint, type checks and tests of the backend and the UI):

```bash
python scripts/check.py
```

Build the installer (needs Inno Setup 7; rebuilds from a clean state; the installer and its SHA-256 go to `packaging/output/`, and the dev server must be stopped):

```bash
python scripts/build_installer.py
```

Releases: the version is `__version__` in `backend/app/__init__.py` (kept equal to `pyproject.toml` and `uv.lock` by a test). Pushing a `v<version>` tag makes GitHub Actions run the checks, build the installer and its `.sha256`, and create a draft Release, which is published by hand. Versions with `-rc.N` are marked as pre-releases.
