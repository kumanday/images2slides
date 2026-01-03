from __future__ import annotations

import threading
import time

from fastapi import FastAPI

from .runner import claim_next_job, run_job

app = FastAPI(title="images2slides worker", version="0.1")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _loop() -> None:
    while True:
        job_id = claim_next_job()
        if job_id is None:
            time.sleep(1.0)
            continue

        try:
            run_job(job_id)
        except Exception:  # noqa: BLE001
            # Any errors should already be recorded on the job.
            pass


@app.on_event("startup")
def start_worker_thread() -> None:
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
