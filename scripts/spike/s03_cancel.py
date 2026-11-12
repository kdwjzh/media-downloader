"""Item 6: cancel during download and during FFmpeg, and what is left on disk."""

import json
import subprocess
import time

from common import BIN, LONG, NO_WINDOW, PROGRESS, fresh, popen

case = 0
LONG_AUDIO = "https://www.youtube.com/watch?v=lzmSKX5TF3g"  # 1 h, so MP3 conversion takes a while


def processes() -> list[dict]:  # type: ignore[type-arg]
    """Processes running from this project's bin/ only (pid, parent pid, name).

    Filtered by executable path so an unrelated yt-dlp or ffmpeg the user is
    running elsewhere is never listed, and never killed by the cleanup below.
    """
    script = (
        "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '"
        + str(BIN)
        + "\\*' } | Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                         text=True, creationflags=NO_WINDOW).stdout.strip()  # fmt: skip
    data = json.loads(out) if out else []
    return [data] if isinstance(data, dict) else data


def describe(label: str) -> list[dict]:  # type: ignore[type-arg]
    found = processes()
    print(f"  {label}: " + (", ".join(f"{p['Name']}(pid {p['ProcessId']} <- {p['ParentProcessId']})" for p in found) or "none"))
    return found


def listing(folder) -> dict[str, int]:  # type: ignore[no-untyped-def]
    return {str(p.relative_to(folder)): p.stat().st_size for p in sorted(folder.rglob("*")) if p.is_file()}


def cancel(title: str, args: list[str], wait_for: str, how: str, temp: bool = False) -> None:
    global case
    case += 1
    folder = fresh(f"cancel{case}")  # one folder per case: a just-killed process may still hold files
    paths = ["-P", f"home:{folder}"] + (["-P", f"temp:{folder / '.tmp-task1'}"] if temp else [])
    print(f"\n## {title} | kill with: {how}")
    process = popen([*args, *paths, *PROGRESS, "-o", "%(title)s [%(id)s].%(ext)s", "--no-playlist"])
    assert process.stdout
    for line in process.stdout:
        if wait_for in line:
            print("  trigger line:", line.strip()[:230])
            break
    time.sleep(0.5)
    describe("before")
    start = time.perf_counter()
    if how == "Popen.kill()":
        process.kill()
    else:
        result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                                text=True, encoding="cp950", errors="replace", creationflags=NO_WINDOW)  # fmt: skip
        print("  taskkill exit:", result.returncode, "|", " / ".join(result.stdout.split("\n"))[:300])
    code = process.wait()
    print(f"  wait() returned {code} after {time.perf_counter() - start:.2f}s")
    time.sleep(1)
    survivors = describe("after 1 s")
    first = listing(folder)
    time.sleep(4)
    second = listing(folder)
    growing = [name for name in second if second[name] != first.get(name)]
    print(f"  files still changing 4 s later: {growing or 'none'}")
    survivors = describe("after 5 s")
    for name, size in second.items():
        print(f"    {size:>13,}  {name}")
    for survivor in survivors:  # clean up so the next case starts clean
        subprocess.run(["taskkill", "/PID", str(survivor["ProcessId"]), "/T", "/F"],
                       capture_output=True, creationflags=NO_WINDOW)  # fmt: skip


if __name__ == "__main__":
    describe("baseline (should be none)")
    mp4 = ["-S", "res:2160", "--merge-output-format", "mp4", LONG]
    mp3 = ["-f", "ba/b", "-x", "--audio-format", "mp3", "--embed-thumbnail", LONG_AUDIO]
    downloading = '"downloaded_bytes": 2'  # some progress line a little way in
    cancel("during download", mp4, downloading, "Popen.kill()")
    cancel("during download", mp4, downloading, "taskkill /T /F")
    cancel("during download, with -P temp:", mp4, downloading, "taskkill /T /F", temp=True)
    cancel("during FFmpeg (MP3 conversion)", mp3, '"ExtractAudio"', "Popen.kill()")
    cancel("during FFmpeg (MP3 conversion)", mp3, '"ExtractAudio"', "taskkill /T /F")
    cancel("during FFmpeg, with -P temp:", mp3, '"ExtractAudio"', "taskkill /T /F", temp=True)
