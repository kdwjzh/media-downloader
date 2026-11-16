# yt-dlp samples

Real output of yt-dlp 2026.10.26, recorded with `scripts/spike/s11_record.py` (2026-11-14).

- Personal paths are replaced with `<TEMP>`, `<REPO>`, `<HOME>`.
- `info/*.json` keep only the fields the engine could read; the kept values are unchanged.
  Format URLs are dropped (they are signed for the recording machine's address).
- `download/*.txt` are stdout and stderr together, the way the engine reads them.
- `download/http_403.txt` was recorded on 2026-11-16 with `s11_record.py forbidden`: five downloads
  at a time until YouTube refused one (the 70th).
- `selected.json` is what yt-dlp itself chose for every MP4 quality of the four sample videos.
- `errors/update_no_permission.txt` is the line recorded on 2026-11-12 (docs/技術驗證.md item 9).
- `*_proxy.txt` and the `retry_*` downloads were produced with a local proxy.
  `errors/offline_*_real.txt` are from really switching Wi-Fi off (the engine's `detail` text).
