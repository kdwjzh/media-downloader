"""YtDlpEngine: the MediaEngine that drives the official yt-dlp executable."""

import threading
from collections.abc import Callable
from pathlib import Path

from app.domain.engine import (
    DownloadCancelled,
    DownloadRequest,
    DownloadResult,
    EngineError,
    EngineEvent,
    OnDuplicate,
)
from app.domain.errors import ErrorCode
from app.domain.media import MediaInfo, PlaylistInfo
from app.infrastructure.engines.ytdlp import args, files, parse, urls
from app.infrastructure.engines.ytdlp.errors import classify
from app.infrastructure.engines.ytdlp.process import JobProcess, run

# Backstops for a process that hangs; the network arguments in args.py end normal failures
# much sooner. A playlist of 1,700 entries takes 11 s to list.
LOOKUP_TIMEOUT = 60
VERSION_TIMEOUT = 20
UPDATE_TIMEOUT = 180


class YtDlpEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: dict[str, JobProcess] = {}
        self._cancelled: set[str] = set()

    def fetch_info(self, url: str) -> MediaInfo | PlaylistInfo:
        urls.check(url)
        try:
            code, out, err = run(args.info(url), LOOKUP_TIMEOUT)
        except TimeoutError as error:
            raise EngineError(ErrorCode.NETWORK, str(error)) from error
        if code != 0:
            raise classify(err)
        return parse.info(url, out)

    def download(
        self, request: DownloadRequest, on_event: Callable[[EngineEvent], None]
    ) -> DownloadResult:
        urls.check(request.url)
        task_dir = files.create_task_dir(request.dest_dir, request.task_id)
        process: JobProcess | None = None
        try:
            # One stream: yt-dlp prints download progress on stdout and post-processing
            # progress on stderr, and the events must stay in order.
            process = JobProcess(args.download(request, task_dir), merge_stderr=True)
            with self._lock:
                self._running[request.task_id] = process
            assert process.popen.stdout

            output = parse.DownloadOutput()
            existing: Path | None = None
            name_checked = False
            for line in process.popen.stdout:
                event = output.feed(line)
                if output.name and not name_checked:
                    name_checked = True
                    wanted = files.target(
                        request.dest_dir, files.final_name(output.name, request.format)
                    )
                    if request.on_duplicate is OnDuplicate.SKIP and wanted.exists():
                        existing = wanted  # known about 5 s before the first byte would move
                        process.kill()
                        break
                if event:
                    on_event(event)
            code = process.popen.wait()

            with self._lock:
                cancelled = request.task_id in self._cancelled
            if cancelled:
                raise DownloadCancelled(request.task_id)
            if existing:
                return DownloadResult(str(existing), existing.stat().st_size, skipped=True)
            if code != 0 or not output.file or not output.name:
                raise classify(output.other_text)
            placed, skipped = files.place(
                Path(output.file),
                request.dest_dir,
                files.final_name(output.name, request.format),
                request.on_duplicate,
            )
            return DownloadResult(str(placed), placed.stat().st_size, skipped)
        finally:
            if process:
                process.kill()
                process.popen.wait()
                process.close()
            with self._lock:
                self._running.pop(request.task_id, None)
                self._cancelled.discard(request.task_id)
            files.remove_dir(task_dir)

    def cancel(self, task_id: str) -> None:
        with self._lock:
            process = self._running.get(task_id)
            if process:
                self._cancelled.add(task_id)
        if process:
            process.kill()  # download() notices, cleans up and raises DownloadCancelled

    def stop_all(self) -> None:
        """For closing the app: cancels every running download."""
        with self._lock:
            task_ids = list(self._running)
        for task_id in task_ids:
            self.cancel(task_id)

    def remove_stale_temp(self, dest_dir: str) -> None:
        """For starting the app: deletes task folders left by a run that ended abnormally."""
        files.remove_stale(dest_dir)

    def version(self) -> str:
        try:
            code, out, err = run(args.version(), VERSION_TIMEOUT)
        except (OSError, TimeoutError) as error:
            raise EngineError(ErrorCode.UNKNOWN, str(error)) from error
        if code != 0 or not out.strip():
            raise EngineError(ErrorCode.UNKNOWN, err.strip())
        return out.strip()

    def update(self) -> bool:
        """True: a newer version was installed. False: already the newest.

        Raises EngineError: NETWORK when GitHub cannot be reached; UNKNOWN for everything
        else, including a folder that cannot be written (exit code 100) and GitHub's hourly
        request limit. The raw output is in .detail.
        """
        try:
            code, out, err = run(args.update(), UPDATE_TIMEOUT)
        except TimeoutError as error:
            raise EngineError(ErrorCode.NETWORK, str(error)) from error
        except OSError as error:
            raise EngineError(ErrorCode.UNKNOWN, str(error)) from error
        return parse.update_result(code, out, err)
