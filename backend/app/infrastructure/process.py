"""Starts an external program inside a Windows Job Object, with no console window.

yt-dlp.exe is two processes deep and starts Deno and FFmpeg itself. The job is how all of
them are stopped together, and how they die with the app even if the app is killed
(docs/decisions/0008).
"""

import ctypes
import subprocess
import threading
from ctypes import wintypes

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_ntdll = ctypes.WinDLL("ntdll")
_kernel32.CreateJobObjectW.restype = wintypes.HANDLE
_kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
_kernel32.SetInformationJobObject.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.LPVOID,
    wintypes.DWORD,
]
_kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
_kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]

_CREATE_SUSPENDED = 0x4
_KILL_ON_JOB_CLOSE = 0x2000
_EXTENDED_LIMIT_INFORMATION = 9


class _BasicLimits(ctypes.Structure):
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


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits),
        ("IoInfo", ctypes.c_uint64 * 6),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class JobProcess:
    """One program and everything it starts. stdout and stderr are UTF-8 text pipes;
    merge_stderr puts both on stdout, in the order they were written."""

    def __init__(self, args: list[str], merge_stderr: bool = False) -> None:
        self._job = _kernel32.CreateJobObjectW(None, None)
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = _KILL_ON_JOB_CLOSE
        if not self._job or not _kernel32.SetInformationJobObject(
            self._job, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        self._lock = threading.Lock()
        try:
            # Suspended until it is in the job, so nothing it starts can be outside of it.
            self.popen = subprocess.Popen(
                args,  # a list, never a shell string
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW | _CREATE_SUSPENDED,
            )
        except OSError:
            self.close()
            raise
        handle = int(self.popen._handle)  # type: ignore[attr-defined]
        if not _kernel32.AssignProcessToJobObject(self._job, handle):
            error = ctypes.WinError(ctypes.get_last_error())
            self.popen.kill()
            self.close()
            raise error
        _ntdll.NtResumeProcess(handle)

    def kill(self) -> None:
        """Ends every process in the job. Safe to call more than once, or after it ended."""
        with self._lock:
            if self._job:
                _kernel32.TerminateJobObject(self._job, 1)

    def close(self) -> None:
        with self._lock:
            if self._job:
                _kernel32.CloseHandle(self._job)
                self._job = None


def run(args: list[str], timeout: float) -> tuple[int, str, str]:
    """Runs to the end; returns (exit code, stdout, stderr). Raises TimeoutError."""
    process = JobProcess(args)
    try:
        out, err = process.popen.communicate(timeout=timeout)
        return process.popen.returncode, out, err
    except subprocess.TimeoutExpired:
        process.kill()
        process.popen.communicate()
        raise TimeoutError(f"no result after {timeout} s") from None
    finally:
        process.kill()
        process.close()
