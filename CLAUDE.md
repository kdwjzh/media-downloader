<!--
What this file is: the project spec and working rules for media-downloader.
Claude Code reads it at the start of every session.
Update it when the spec or a decision changes; when you hit a pitfall, write "don't do this again" as a rule.
Published on GitHub: yes, but never put tokens, personal paths or account data in it.
When the code and this file disagree, change one of them; this file is the reference.
-->

# CLAUDE.md: media-downloader

A Windows desktop downloader, mainly for music and also for video, that uses a download queue to handle many songs and whole playlists at once.

This file holds the decisions and rules. Details are in `docs/功能規格.md` (spec), `docs/架構.md` (architecture), and the background of each decision in `docs/decisions/`.
Everything under `docs/` and `design-system/` is written in Traditional Chinese.
When `docs/` disagrees with this file, this file wins; bring `docs/` in line. Ask before adding a feature the documents don't describe.

## 1. Goals

- Replace the earlier project youtube-downloader (Python + CustomTkinter), which was hard to maintain and had bugs in daily use.
- Mostly for music (MP3), sometimes video (MP4); many URLs can be queued at once, and whole playlists downloaded.
- Users are the author and people who download the installer from GitHub. They may not have Python.
- YouTube first; the architecture leaves room for other platforms (TikTok, Instagram, X, Telegram, …).
- Also a practice project for a UI design workflow.

### Not doing

- A format converter.
- A help window with picture tutorials, or a menu bar (docs / about / check for updates live on the settings screen).
- Testing or supporting platforms other than YouTube in the first version.
- Not in the first version: automatic MP3 tagging, original audio formats (m4a / opus), dark mode, searching the history, Windows notifications, subtitles, trimming to a time range, signing in with browser cookies.
- No silent background updates of the app; a new version is only announced inside the app.
- No "download a zip and run a .bat" release.

## 2. Decisions

| Item | Decision | Reason |
| --- | --- | --- |
| Name | repo `media-downloader`, app name Media Downloader | Says what it does, not tied to one platform |
| Language / framework | Backend Python 3.12+; UI React + TypeScript + Vite + Tailwind | Download logic stays in Python; a web UI makes the UI design workflow usable. See `docs/decisions/0001` |
| Desktop shell | pywebview (WebView2 on Windows) | One process, two languages; easier to maintain than Tauri. See `0002` |
| Download engine | Run the official yt-dlp executable with Deno and FFmpeg; never `import yt_dlp` | yt-dlp can be updated on its own, and cancelling is ending a process. See `0003` |
| Where external programs live | The installer installs "for the current user only" into `%LOCALAPPDATA%\Programs`; external programs go in the shared folder `%LOCALAPPDATA%\media-downloader\bin` (the repo's `bin\` during development) | Updating the app (running the installer again) never puts back an older yt-dlp the user already updated. See `0018` (replaces `0005`) |
| UI state | Zustand | Light; the queue state lives in one place |
| UI languages | Traditional Chinese and English, react-i18next, follows the system by default | Other people use it |
| Visual direction | "Record sleeve": plum as the main color, square MP3 thumbnails, MP4 stays 16:9; the rules are in `design-system/media-downloader/` | Its character comes from its purpose, getting music. See `0006` |
| Fonts and icons | Noto Sans TC and Bricolage Grotesque ship with the app (npm packages), icons are Phosphor; nothing is loaded from the internet | Looks the same on every computer and works offline. See `0006` |
| Window | 960x680 by default, 720x520 minimum, navigation on the left | List screens need height more than width. See `0006` |
| Storage | Settings as JSON and history in SQLite (thumbnails included), in `%APPDATA%`; the log and the new-version check result in `%LOCALAPPDATA%` | SQLite ships with Python, and the history can be searched later. See `0011` |
| New-version check | Ask GitHub for the latest release and keep the answer 24 hours (1 hour when there was no answer); the version is `__version__` in `backend/app/__init__.py`, compared as semantic versions (`1.0.0-rc.1 < 1.0.0`) | No network call on every start; a packaged app has no `pyproject.toml`. See `0011`, `0019` |
| App update | "Update now" on the settings screen: download the installer from the release, check it against `.sha256`, run it with `/SILENT`, the app closes and reopens after the install; a packaged app updates yt-dlp when it starts (once a day) | Users don't have to download installers themselves; an outdated yt-dlp is the most common cause of breakage. See `0019` |
| Download processes | Every external program runs in its own Windows Job Object; cancelling ends the whole Job | When the app is killed, its downloads end too. See `0008` |
| File names and duplicates | The file name is the title only; a download finishes in the task's temporary folder and the engine applies skip / overwrite / rename when it moves the file into the download folder | No half-finished files in the download folder, and the user's existing files are left alone. See `0009` |
| MP3 cover | A JPEG cropped to a centered square | Matches the square "record sleeve" thumbnails |
| Tests | pytest for the backend, Vitest for the UI | |
| Packaging / release | PyInstaller (folder mode) + an installer; pushing a tag makes GitHub Actions build and upload to Releases | Users don't need Python |
| Implementation order | Skeleton → technical spike → UI design → backend → UI → packaging | UI design needs real data to work from. See `0004` |
| License | MIT; the bundled yt-dlp, FFmpeg, Deno, the two fonts (OFL 1.1) and the Python and npm packages keep their own licenses, which the README and the about screen point to | A personal tool; the simplest permissive license. See `0021` |
| Public | Private during development, public when done. English: README.md, CHANGELOG.md, CLAUDE.md; README.zh-TW.md, `docs/` and the design system stay in Chinese | See `0021` |

Look up the current stable version of a package when you add it; don't write versions from memory.

## 3. Spec

The full spec and the table of the old version's bugs are in `docs/功能規格.md`. First version:

- Download queue: paste many URLs in a row; each item has its own progress and can be cancelled or retried; cancel everything at once (after a confirmation); the number of simultaneous downloads is a setting.
- Playlists: a pasted URL expands into queue items, and you tick which ones to download.
- MP3 and MP4; the audio / video qualities offered are the ones that video actually has, with an estimated file size.
- Video preview (thumbnail, title, length, channel); music files can embed the cover.
- Remember the last format, quality and folder.
- History: download again, open the containing folder, delete one entry, clear.
- Settings: download folder, default format and quality, simultaneous downloads, what to do with duplicate files, UI language, check for updates, about.
- Duplicate files: skip / overwrite / rename automatically.
- Error messages are grouped by cause and say what to do next (private video, age restriction, members only, region restriction, network lost).
- yt-dlp can be updated on its own; a new app version is announced inside the UI, not in a pop-up.
- Progress is one overall bar with the current stage: the download stage shows a real percentage; looking up info, converting, merging and embedding the cover have no percentage and show the stage name with an indeterminate bar, never a fake number.
- The installer includes every external program; no console window ever appears.

Screens: main (paste a URL + queue), empty state, playlist selection, history, settings.

Done means: every old-version problem in section 2 of `docs/功能規格.md` (U1–U4, C1–C11) checked one by one.

## 4. Architecture

Details in `docs/架構.md`. Commands, events and data shapes between the UI and the backend follow `docs/介面與後端的約定.md` (the contract).

```
UI frontend/  →  bridge bridge/  →  services services/  →  domain domain/  ←  infrastructure infrastructure/
```

```
backend/app/
  bridge/            between the UI and the backend; no business logic
  services/          queue, video info, history, settings, updates
  domain/            models and rules: DownloadTask (state machine), MediaInfo, ErrorCode, the MediaEngine interface
  infrastructure/
    engines/ytdlp/   YtDlpEngine, implements MediaEngine
    storage/         settings file, history database, folder locations
    binaries/        paths and versions of the external programs
    logging/         log file (with personal paths masked)
    process.py       the only way to start an external program (Job Object)
    http.py          the only way the app itself reaches the network
    thumbnails.py releases.py shell.py   history thumbnails, latest release, opening things with Windows
    app_installer.py   download, check and start the installer of a new app version
  composition.py     wires all the services together (real engine, files, Windows)
backend/tests/
frontend/src/
  api/               the only place that calls the bridge
  pages/ components/ stores/ i18n/
design-system/       UI design rules (MASTER.md and pages/)
brand/               app icon (logo/, icons/, concepts/, guidelines.md)
docs/                spec, architecture, decision records, technical spike
packaging/           PyInstaller spec, installer script, licenses
scripts/             one-step check, fetching external programs, developer commands
```

### Dependency direction (never break)

1. An upper layer may call a lower one; a lower layer never imports an upper one.
2. A lower layer tells an upper one about something only by emitting an event, never by calling it.
3. `domain/` never touches files, the network or subprocesses.
4. Only `infrastructure/engines/ytdlp/` may contain yt-dlp options, output formats or error strings.
5. `bridge/` holds no business logic.
6. In the UI only `frontend/src/api/` may call the bridge; every other component goes through it.
7. Paths of external programs come only from `infrastructure/binaries/`.
8. Only `DownloadTask`'s state machine changes a task's status.
9. The backend returns error codes (`ErrorCode`), never text for people; the text lives in the UI's language files.
10. The engine never touches `DownloadTask` directly: it reports events and the service layer applies them to the task.
11. Finished file paths are never handed to the UI; the UI asks the backend to open a folder by task id or history id.
12. `services/` never imports `infrastructure/`: what it needs is defined as an interface in `services/ports.py`, and `composition.py` plugs in the real implementation.
13. The app reaches the network only through `infrastructure/http.py` (https, a host allow-list, at most 5 redirects each checked again, a size limit). Certificates are verified by Windows through truststore; don't go back to Python's default SSL setup: it fails on a clean Windows that lacks a root certificate (`0020`).

Constants that exist on both sides (formats, audio qualities, video qualities, the nine statuses, the 13 error codes, which errors can be retried) live in `backend/app/domain/` and `frontend/src/types.ts`; change both together.
The status transition table must match in three places: `TRANSITIONS` in `domain/task.py`, section 6 of the contract, and the state diagram in `架構.md`.

Before adding a file, say which layer it belongs to. If a requirement seems to need breaking these rules, stop and ask.

### Multiple platforms

Download engines implement the `MediaEngine` interface. The first version only has `YtDlpEngine`. `MediaInfo` carries a `platform` field.
Internal names (classes, tables, setting keys) never use "youtube" as a general name; YouTube is just one platform.

## 5. Rules

### Security

- Tokens, cookies, account data and personal paths never go into git or into the log.
- External executables (yt-dlp, FFmpeg, Deno) never go into git; `scripts/` downloads them and checks the hash their source publishes.
- External programs are always called with an argument list, never a shell command built from strings; URLs and paths from the user are passed only as single arguments.
- A file name taken from a video title has the characters Windows forbids removed, and the result must still be inside the download folder the user chose.

### Tests

- Every bug first gets a failing test that reproduces it; that test stays forever.
- Run the one-step check `scripts/check.py` before calling anything done.
- `backend/tests/test_layering.py` checks the dependency direction; when it fails, change the code, not the lists in the test (unless the rule itself changed).
- Logic in `domain/` and `services/` has pytest tests; tests never use the network, and yt-dlp output comes from recorded samples.

- Tests involving threads never `sleep` or assume which thread runs first: use `tests/fake_engine.py` (each step is driven by the test) and an injected fake clock. Run a new queue test dozens of times to be sure it never fails now and then.
- File names in `tests/` and `scripts/manual/` must not match a standard library module (e.g. `queue.py`): that folder comes first on the import path, so even the standard library's own `import queue` would import it.

### Queue (reasons in `docs/decisions/0010`)

- A task is changed only while holding `QueueService`'s lock; events are also queued inside the lock. Nothing that may be slow or call back into the queue (UI listeners, history) is called inside the lock.
- The engine's `on_event` handler must not raise or do anything slow: an exception aborts the download.
- Two downloads with the same task id must never overlap (they share a temporary folder): free slots are counted by download threads still alive, and a re-added task waits for the previous round to end.
- Progress throttling drops what arrives too early; don't change it to hold and send later: that sends an old percentage after the status changed.
- Background threads are always daemon threads; no `ThreadPoolExecutor`, which makes the app wait at exit for processes still looking things up.
- The settings implementation (`QueueSettings`) is read by the queue inside its lock; it must not call back into the queue or take a lock that waits on the queue.

### Settings, history, log (reasons in `docs/decisions/0011`)

- Reading settings takes no lock (the whole object is replaced at once); the only lock order is "settings write lock → queue lock". Settings listeners are called inside the write lock and must not change settings.
- Before a downloaded image goes to FFmpeg, check its header and name the format with `-f`: left to guess, FFmpeg can be made to read other files by a format such as a playlist.
- The history database is renamed and started fresh only when it is certainly damaged (not a database, corrupt content); a full disk or a lock doesn't count.
- Files, folders and web pages are opened without building a command line (no `explorer /select,`): use `infrastructure/shell.py`.
- The log never records titles or file paths; a new log line that may contain a path relies on the masking in `logging/setup.py`, not on its own handling.
### Bridge (reasons in `docs/decisions/0012`)

- pywebview exposes every attribute of `BridgeApi` that doesn't start with an underscore to the page (and their attributes too): every member that isn't a command starts with an underscore. `test_bridge_api.py` checks that the exposed names are exactly the contract's commands.
- Every command is wrapped by `_run`, so no exception leaks into the page.
- `emit` only queues; it never calls services or waits for the page. Only the `EventSender` thread sends events.
- The `closing` handler runs synchronously on the UI thread: it must not call `evaluate_js` or anything that waits for the page (deadlock).
- The bridge doesn't import pywebview: what needs the window is wrapped as functions by `main.py` and passed in.
- When a data shape, event or command name changes, change `types.ts` and `api/index.ts` too; `test_types_ts.py` catches it.

- Tests and `scripts/manual/` never use the default folders: pass temporary folders to `build()`. `Backend.start()` clears temporary files in the download folder; never call it on the real Downloads folder in a test.

### Workflow

- One feature or fix at a time; say which files will change before starting.
- Changes users can see go into `[Unreleased]` in `CHANGELOG.md`.
- Major decisions go into `docs/decisions/NNNN-title.md`.
- Follow the order in section 2 one stage at a time, never across stages; at the end of each stage, say how to accept it.

### UI text

- Every text shown to users lives in `zh-TW.json` and `en.json` under `frontend/src/i18n/`; add to both together.
- No hard-coded Chinese or English strings in components.
- Change `README.md` and `README.zh-TW.md` together; they match section by section (`0021`).

### External programs

- Every external program runs with its console window hidden, and its output is read as UTF-8.
- Check yt-dlp options in the official documentation; don't write them from memory.
- Pitfalls of calling yt-dlp (reasons in `docs/技術驗證.md`):
  - Always pass `--ignore-config`, `--encoding utf-8`, `--color never`, `--ffmpeg-location`; without `--encoding utf-8` the output is the system's cp950.
  - Name Deno with `--js-runtimes deno:<absolute path>`; a relative path isn't found.
  - `--print` switches to quiet mode, which hides the download progress and the "retrying" line; add `--no-quiet` and `--progress`.
  - Download progress goes to stdout and post-processing (conversion, merging) progress to stderr: while downloading, read the two merged into one stream, in order.
  - Cancelling must end the whole process tree: `yt-dlp.exe` is two processes, and ending only the outer one leaves the inner one and FFmpeg running. External programs always start through `infrastructure/process.py`, inside a Job Object, never with `subprocess` directly and never with `taskkill` (see `0008`).
  - Each task uses its own temporary folder (`<download folder>\.md-tmp-<task id>`); the whole download happens inside it, and the engine moves the result out applying the duplicate rule; the folder is deleted after a cancel, a failure or a success (see `0009`).
  - The exit code of every failure is 1; errors are classified by the text after `ERROR:`. That line may be empty with the text on the next one, so read the whole block. Matching rules live only in `errors.py`. Anything unmatched is an unknown error, with the original text in the log.
  - The count in the brackets of the retry line starts again from 1; the engine counts the retries itself.
  - MP3 cover conversion happens before the download; "conversion started" only counts post-processing after the download started.
  - On HTTP 403 during a download (about 1 in 15 with 3 or more at once) the engine tries once more by itself: only before any progress, at most once, and the second failure is reported as usual. This lives only in the engine; the service layer doesn't know. The strings it checks are in `errors.py`. Between the two attempts the task is still running, so a cancel isn't missed.
  - An upcoming live stream fails outright (`This live event will begin in …`) instead of returning `live_status=is_upcoming`; both paths must map to `liveNotSupported`.
  - yt-dlp splits the value of `--ppa` like a shell: when an FFmpeg filter contains commas, use double quotes outside and single quotes inside.
  - A URL given to yt-dlp first passes `urls.check` (http/https, the YouTube domain list) and comes after `--`.
  - Quality uses `-S res:N,vcodec:h264,acodec:m4a` with `--merge-output-format mp4`, not `height<=N` (which picks wrong for vertical videos). 4K has no H.264, so it is VP9 inside mp4, without re-encoding.
- ffprobe doesn't ship with the app: adding an MP3 cover and merging an MP4 don't need it. Add it back when a later feature needs it.

### Packaging and installer (reasons in `docs/decisions/0018`)

- One-step build: `python scripts/build_installer.py`, starting by deleting `build/`; the output goes to `packaging/output/` (not in git). It runs `npm ci`, so stop the dev server first.
- Change the version only in `__version__` in `backend/app/__init__.py` and in `pyproject.toml` (`test_version.py` catches a mismatch); `uv run` also changes the version in `backend/uv.lock`, so commit or revert it together. The installer's version is passed in by the build script, never written into `installer.iss`.
- The yt-dlp line in `installer.iss` must **not** get `ignoreversion`: Inno's version comparison is what keeps it from replacing a newer one the user updated. FFmpeg and Deno do get it.
- Data files of the packaged app are under `sys._MEIPASS` (`_internal\`), not anywhere reachable by walking up from `__file__` (`DIST_INDEX` in `main.py`).
- When FFmpeg's version changes, change `fetch_binaries.py` and `packaging/licenses/FFmpeg-SOURCE.txt` together (the source link must point at the build actually shipped).
- `installer.iss` contains Chinese; save it as UTF-8 with a BOM.
- The mutex name created in `main.py` and `AppMutexName` in `installer.iss` must match.
- Releases are built by `.github/workflows/release.yml` (reasons in `0020`): pushing a `v*` tag creates a draft Release; a manual run only keeps an artifact. A draft is published only by a manual run with the `publish` input (the tag), which checks the two files before and after (`0022`); not from a web edit page: a draft's page is `releases/edit/untagged-…`, and `releases/edit/<tag>` for a tag that only has a draft makes a second, empty release (v1.0.0 has no installer because of it). Release notes are pasted after publishing, on `releases/edit/<tag>`, once that page lists both files. Only the installer and its `.sha256` are uploaded; the workflow never gets `--test-update-source` (`test_update_source.py` catches it).
- Without `--test-update-source`, `build_installer.py` checks that `packaging/output/` holds only those two files and that Inno's file list (`OutputManifestFile`) has no marker file; `--release-tag` must equal `v<__version__>`. Don't remove these checks.
- uv.lock writes the version the PEP 440 way (`1.0.0rc1`); `test_version.py` normalizes it before comparing. Change all three together.
- Actions in workflows are pinned to commit SHAs; Inno Setup (7.1.1) and gitleaks (8.30.1) have their version and SHA-256 written in. Change the hashes when upgrading.
- The exe's version information is made by the spec from `__version__`; the numeric version has only the first three parts (`x.y.z.0` for rc and final alike). No email or personal data in it.
- The `.sha256` is written with LF line endings: GNU `sha256sum -c` before coreutils 9.0 rejects CRLF (`test_build_installer.py`).
- Third-party licenses (`0021`): `build_installer.py` writes `build/licenses/` — the license files of every Python package the backend needs (walked from `pyproject.toml`'s dependencies, as installed in `backend/.venv`) plus Python's own, and the npm packages Vite bundled (`build.license` in `vite.config.ts`). The build fails if a package has no license file; a package that ships none gets one kept in `packaging/licenses/` and listed in `SEPARATE_LICENSES`. The installer puts both folders into `{app}\licenses`.

### App updates (reasons in `docs/decisions/0019`)

- The installer and checksum URLs are built from the version only (`releases.py`), after the version passes `domain/version.py`. Don't switch to URLs or file names from GitHub's response.
- A checksum that doesn't match, can't be read, or a download that isn't complete: never run it, delete the downloaded file. The failure path has no "run it anyway" exception.
- The installer starts with `process.launch_detached()`, **never** `JobProcess`: when the app ends, the Job would end the installer too.
- The app starts the installer **without** `/SUPPRESSMSGBOXES`: it makes the answer to the "close the app" box Cancel, and the installer quietly ends.
- Don't remove `AllowCancelDuringInstall=no` from `installer.iss`: when Inno cancels, it doesn't restore replaced files or the `_internal` deleted by `[InstallDelete]`, and the app won't start.
- The installer's wait for the app to end is in `InitializeSetup`: after it, Inno checks AppMutex only once.
- The test update source can only be switched on by `build_installer.py --test-update-source` (marker file `update-source-test`, the same name in three places); `…-TEST.exe` is never uploaded. `test_update_source.py` catches it.
- `http.py` allows http in one case only: the test source's `127.0.0.1`, and only when the caller explicitly passes `loopback_http=True`.
- The host list for downloading the installer uses full names; never add `githubusercontent.com` (`raw.githubusercontent.com` serves anyone's files).
- Automatic yt-dlp updates run only in a packaged app (`main.py`); during development the yt-dlp in `bin/` must not change by itself.

### Releasing a new version (reasons in `0020`, `0022`)

Pushing the tag and publishing can't be undone: ask the author before each. A published tag or Release is never deleted or changed (only its notes); a problem means a new version. The repo has immutable releases on: a published Release's files and tag are locked, and a deleted one's tag name can't be used again.

1. Pick the version from what `[Unreleased]` holds (SemVer: a fix → patch, a feature → minor).
2. Change it in the three places: `__version__` in `backend/app/__init__.py`, `backend/pyproject.toml`, `backend/uv.lock` (PEP 440 form there: `1.2.0rc1`).
3. CHANGELOG: `[Unreleased]` becomes `[x.y.z] - YYYY-MM-DD` with the day the tag is pushed (change it again if the tag slips to another day); a new empty `[Unreleased]` goes above it; the links at the bottom get `[Unreleased]: …/compare/vx.y.z...HEAD` and `[x.y.z]: …/compare/v<previous>...vx.y.z`.
4. `python scripts/check.py`, commit (noreply author, gitleaks), push, and wait for CI to pass.
5. Push an annotated tag `vx.y.z` on that commit. `release.yml` must succeed in both jobs, with `MediaDownloader-Setup-x.y.z.exe: OK` in the release job's log; the draft holds exactly the installer and its `.sha256`, and is a pre-release only for `-rc.N`.
6. Publish: Actions → Release → Run workflow on `main`, `publish` = the tag. Never a web edit page (see the Packaging rules).
7. Paste the notes on `releases/edit/vx.y.z` once that page lists both files: the CHANGELOG section, with an Install line pointing to the README.
8. Check after publishing:
   - `api.github.com/repos/<repo>/releases/latest` returns the tag, `immutable: true`, two assets.
   - Download both files from `releases/download/vx.y.z/…`: `sha256sum -c` prints OK, and every redirect host is in `download_hosts` in `releases.py` (if not, stop and report; don't widen the list).
   - On a clean Windows (Sandbox), follow the English README: install, download a song, About shows the version.
   - One-click update from the previous version. The installed app caches the version check for 24 hours: delete `%LOCALAPPDATA%\media-downloader\update-check.json` before starting it, or use a fresh Sandbox.
   - Windows Sandbox's WebView2 registration can point to a version that isn't there (white window, "Couldn't find a compatible Webview2 Runtime" in the log). Start the app from a PowerShell that set `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` to the folder under `%ProgramFiles(x86)%\Microsoft\EdgeWebView\Application`; the installer and the reopened app inherit it.

### UI workflow (ui-ux-pro-max + frontend-design)

Framework for this project: react
Design rules: `design-system/media-downloader/MASTER.md` (screen-specific rules under `pages/` override MASTER)

Before any UI work:

1. Read MASTER.md first; if there is a matching `pages/<screen>.md`, it wins.
2. Look up rules with ui-ux-pro-max: `--stack react`, `--domain web`, `--domain ux`.
3. Don't regenerate the design system or overwrite MASTER.md with `--force`; ask before changing it.

Implementation rules (reasons in `MASTER.md`, set when the stage 2 mock-ups were checked):

- Colors come only from the semantic variables in `frontend/src/index.css`; no color codes in components. Work out the contrast of any new text/background pair first and add it to MASTER's contrast table.
- Mustard yellow is only the background of the MP3 tag; the divider color is never a control border. Neither has enough contrast.
- Queue rows have a fixed height (72) that no status may change; the preview block likewise (172).
- Buttons repeated in a list carry the item's title in their `aria-label`.
- UI state lives in `frontend/src/stores/` (Zustand); components act through stores, and stores call the backend through `api/`. `start()` is called outside React in `main.tsx`, so events still arrive when a screen breaks. Reasons in `docs/decisions/0013`.
- The close confirmation (`ConfirmCloseDialog`) sits **outside** the main content's error boundary and subscribes to `onCloseRequested` itself: when it breaks it stops subscribing, so `api/` closes the window directly. Don't move the subscription into a store, or a broken screen leaves a window that can't be closed.
- The pre-update confirmation (`AppUpdateDialog`) also sits outside the screens: the installer may be ready while the user is on another screen, and a `<dialog>` inside a `hidden` screen never shows.
- The preview's "currently chosen format" lives in the store, not the component: pasting URLs in a row uses it to add automatically.
- A late `lookup` result is dropped by its lookup number; a new lookup, closing the preview and adding to the queue all move the number forward.
- Component tests use jsdom (`// @vitest-environment jsdom` at the top of the file) and test the real `api/` and stores against a fake `window.pywebview.api`. jsdom has no `<dialog>` `showModal()`; tests provide it.
- pywebview window sizes include the title bar and frame: a 960x680 page is really about 947x645, and 720x520 about 707x485.
- Lists that may exceed 100 rows use `frontend/src/virtual.ts` (fixed row height), no extra package; pass it the focused row to keep, or focus is lost when it scrolls away. Reasons in `docs/decisions/0014`.
- When calling the bridge for many items, send them together (`Promise.all`), not one after another: a round trip is about 0.1 s, so 93 of them take 9.8 s.
- Sending events into the page one at a time costs about 17 ms each, so `EventSender` merges queued `tasksChanged` into one (`0014`). The UI's `tasksChanged` handling must not scan the whole queue for each task (use a Map): one event may carry thousands of tasks.
- For a confirmation opened with the mouse, Chromium gives the button focus but draws no focus ring (`:focus-visible` looks at whether the last input was the keyboard). `ConfirmDialog` calls `blur()` and then `focus({ focusVisible: true })`: `showModal()` already focused the first button, so calling `focus()` on it again changes nothing. jsdom can't check this; check it in the real window with a real mouse click.
- A closed `<dialog>` is still in the DOM: tests find buttons in a confirmation with `within(dialog)`, and when finding a button by text, leave out the ones inside `dialog`.
- Where focus moves on to the next button of the same kind after an action (deleting in history), where focus stays on the same element but it becomes another action (buttons in a queue row: Cancel → Add again), and for toggling keys (Space in the playlist), ignore the repeats from holding a key down (`preventDefault()` in `onKeyDown` when `e.repeat`); otherwise holding Enter keeps deleting. Don't return `false` from an `onkeydown` attribute: that blocks the first press too.
- Buttons in a queue row change with the status, and the first one has `key="first"` in every status: React then keeps the same element and focus stays in the row. Removing the key, or putting a conditional element such as `false` before it, drops focus onto the page (the focus test in `components.test.tsx` catches it). Reasons in `docs/decisions/0017`.
- The in-row block showing the full text (`rowTitle.tsx`) is `position: fixed` over the text column: the list itself scrolls (`overflow`), so with `absolute` the part taller than the row is clipped and the list grows a scroll bar. It is therefore closed on scroll (capture) and window resize; while shown it is measured again on every render (when the status changes the buttons change, and with them the text column's width and what is cut off; without measuring again it covers the new buttons). No ancestor of a row may get a `transform`, or `fixed` is trapped inside it.
- Counts that may reach thousands are written `{{count, number}}` in the language files (thousands separators).
- Every screen stays mounted and the others are hidden with `hidden` (`stores/page.ts`): switching back keeps the preview, the ticks and the scroll position. Don't switch to rendering by screen, or everything starts over when you leave. Reasons in `docs/decisions/0015`.
- When focus has to move to "the element that will be there after the delete", note the target before calling the backend: the store redraws the list as soon as it changes, and noting it after the `await` is too late.
- Measure in-row text in the English UI at the smallest window (707 wide): a history row has three buttons, leaving about 160 px for the title.
- A button that must be disabled after a press while focus is still on it ("Check for updates") uses `aria-disabled` with `pointer-events-none`, not `disabled`: `disabled` drops focus onto the page.
- Settings controls change the store to what the user chose first, then call `update_settings` (`changeSettings` in `stores/settings.ts`): waiting for the reply makes radio buttons jump back to the old value first. In tests, a fake `update_settings` must remember earlier changes, or every reply sets the other fields back to their defaults.
- `get_about` starts three programs the first time (about 1.5 s); call it only the first time the settings screen opens. Call it again after `update_engine` succeeds, because the backend forgets the version after an update (`0016`).
- This project has no jest-dom: tests use `.checked`, `.value`, `.textContent`, `getAttribute`, not `toBeChecked()` and the like.

Visual decisions:

- Colors, fonts, layout, amount of motion and UI copy follow frontend-design.
- ui-ux-pro-max's `--design-system` output is only a candidate; ignore the landing-page layouts it gives for app screens.

When rules conflict:

- Accessibility, platform conventions and framework practice follow ui-ux-pro-max.
- Colors, fonts, layout, amount of motion and UI copy follow frontend-design.
- What the author explicitly asks for beats both.

Before delivering:

- Text contrast 4.5:1, large enough click targets, visible focus, respect for reduced motion.
- Button text says what the action does, and the same action uses the same word throughout.
- Error messages say what went wrong and how to fix it; empty screens lead to the next step.

### App icon

- Colors follow `design-system/media-downloader/MASTER.md`.
- When an app icon is needed, use the files in `brand/` (on Windows, `brand/icons/app.ico`); never redraw it.
- Use logo-design only when the author explicitly asks for icon or brand work.
