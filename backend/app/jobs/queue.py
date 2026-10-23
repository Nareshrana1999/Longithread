"""A small in-process background job runner.

Document imports and task batches can be slow; this lets the API accept work
without blocking the request. Deliberately minimal - a single process, bounded
thread pool, in-memory status. Production replaces it with Celery/RQ/queue +
durable status store; the endpoint contract stays the same.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"          # queued | running | done | error
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    finished_at: datetime | None = None


class JobRunner:
    def __init__(self, max_workers: int = 2):
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, func: Callable[[], Any]) -> str:
        job = Job(id=str(uuid.uuid4()), kind=kind)
        with self._lock:
            self._jobs[job.id] = job

        def _run():
            job.status = "running"
            try:
                job.result = func()
                job.status = "done"
            except Exception as exc:  # surface, don't crash the worker
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = "error"
            finally:
                job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)

        self._pool.submit(_run)
        return job.id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False)


default_runner = JobRunner()
