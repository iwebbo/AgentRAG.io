"""
Scheduler worker entry point.

    python -m app.services.scheduler.worker

Runs in its own Deployment (same Docker image as the backend). Safe to run
with several replicas: due tasks and queued runs are claimed with
SELECT ... FOR UPDATE SKIP LOCKED.
"""
import logging
import os

from app.services.scheduler.engine import SchedulerEngine


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    SchedulerEngine().run_forever()


if __name__ == "__main__":
    main()
