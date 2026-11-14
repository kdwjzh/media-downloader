"""Stage 3b, experiment B: taskkill /T /F versus a Windows Job Object.

Main question: when the app itself is force-killed, do its downloads stay behind?

  python s08_tree.py            run every case
  python s08_tree.py app MODE PHASE   (internal) plays the app; MODE is plain or job
"""

import ctypes
import subprocess
import sys
import threading
import time
from ctypes import wintypes

from common import BASE, LONG, NO_WINDOW, PROGRESS, fresh
from s03_cancel import LONG_AUDIO, describe, listing

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]

CREATE_SUSPENDED = 0x4
KILL_ON_JOB_CLOSE = 0x2000
EXTENDED_LIMIT_INFORMATION = 9


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", BasicLimits),
        ("IoInfo", ctypes.c_uint64 * 6),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def new_job() -> int:
    """A job whose processes all die when its last handle closes (i.e. when we die)."""
    job = kernel32.CreateJobObjectW(None, None)
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(job, EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits))
    assert job and ok, ctypes.get_last_error()
    return job


def start(args: list[str], job: int | None) -> subprocess.Popen[str]:
    # Suspended until it is in the job, so it cannot spawn its inner process outside of it.
    flags = NO_WINDOW | (CREATE_SUSPENDED if job else 0)
    process = subprocess.Popen([*BASE, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace",
                               creationflags=flags)  # fmt: skip
    if job:
        handle = int(process._handle)  # type: ignore[attr-defined]
        assert kernel32.AssignProcessToJobObject(job, handle), ctypes.get_last_error()
        assert ntdll.NtResumeProcess(handle) == 0
    return process


def command(phase: str, folder) -> tuple[list[str], str]:  # type: ignore[no-untyped-def]
    paths = ["-P", f"home:{folder}", "-P", f"temp:{folder / '.tmp'}", "-o", "%(title)s.%(ext)s", "--no-playlist"]
    if phase == "download":
        return ["-S", "res:2160", "--merge-output-format", "mp4", LONG, *paths, *PROGRESS], '"downloaded_bytes": 2'
    return ["-f", "ba/b", "-x", "--audio-format", "mp3", LONG_AUDIO, *paths, *PROGRESS], '"ExtractAudio"'


def app(mode: str, phase: str) -> None:
    """Plays the app: starts one download, says READY, then just keeps reading its output."""
    args, trigger = command(phase, fresh(f"tree-{mode}-{phase}"))
    process = start(args, new_job() if mode == "job" else None)
    assert process.stdout
    tail: list[str] = []
    for line in process.stdout:
        tail = [*tail[-5:], line.strip()[:300]]
        if trigger in line:
            print("READY", flush=True)
    print("ENDED", process.wait(), " | ".join(tail), flush=True)
    time.sleep(600)


def app_killed(mode: str, phase: str) -> None:
    print(f"\n## app force-killed during {phase}, children started with: {mode}")
    folder = fresh(f"tree-{mode}-{phase}")  # the app re-creates it; this is just the path
    playing = subprocess.Popen([sys.executable, __file__, "app", mode, phase], stdout=subprocess.PIPE,
                               text=True, creationflags=NO_WINDOW)  # fmt: skip
    assert playing.stdout
    said = playing.stdout.readline().strip()
    if said != "READY":
        print("  the download ended before the trigger:", said)
        playing.kill()
        return
    time.sleep(0.5)
    describe("before")
    # No /T: this is what Task Manager's "End task" or a crash does to the app alone.
    subprocess.run(["taskkill", "/PID", str(playing.pid), "/F"], capture_output=True, creationflags=NO_WINDOW)
    for wait in (1, 5, 20):
        time.sleep(wait if wait == 1 else wait - (1 if wait == 5 else 5))
        before = listing(folder)
        time.sleep(1)
        growing = [n for n, size in listing(folder).items() if size != before.get(n)]
        survivors = describe(f"after {wait} s")
        print(f"    files still growing: {growing or 'none'}")
    for survivor in survivors:
        subprocess.run(["taskkill", "/PID", str(survivor["ProcessId"]), "/T", "/F"],
                       capture_output=True, creationflags=NO_WINDOW)  # fmt: skip


def cancel(how: str, phase: str) -> None:
    print(f"\n## cancel during {phase} with: {how}")
    folder = fresh(f"tree-cancel-{phase}")
    args, trigger = command(phase, folder)
    job = new_job() if how == "TerminateJobObject" else None
    process = start(args, job)
    assert process.stdout
    for line in process.stdout:
        if trigger in line:
            break
    threading.Thread(target=process.stdout.read, daemon=True).start()
    time.sleep(0.5)
    describe("before")
    begin = time.perf_counter()
    if job:
        kernel32.TerminateJobObject(job, 1)
    else:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
    code = process.wait()
    print(f"  wait() returned {code} after {time.perf_counter() - begin:.3f}s")
    describe("right after")
    import shutil

    for attempt in range(20):  # can the task folder be deleted straight away?
        try:
            shutil.rmtree(folder)
            print(f"  folder deleted {time.perf_counter() - begin:.3f}s after the cancel (attempt {attempt + 1})")
            break
        except OSError as error:
            last = error
            time.sleep(0.1)
    else:
        print("  folder could not be deleted:", last)


if __name__ == "__main__":
    if sys.argv[1:2] == ["app"]:
        app(sys.argv[2], sys.argv[3])
    else:
        describe("baseline (should be none)")
        for phase in ("download", "ffmpeg"):
            for mode in ("plain", "job"):
                app_killed(mode, phase)
        for phase in ("download", "ffmpeg"):
            for how in ("taskkill /T /F", "TerminateJobObject"):
                cancel(how, phase)
        describe("at the end (should be none)")
