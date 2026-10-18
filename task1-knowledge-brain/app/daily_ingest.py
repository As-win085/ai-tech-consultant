"""Long-running UTC daily trigger; schedule with Task Scheduler or a service manager."""

from datetime import datetime, time as day_time, timedelta, timezone
import time

from app.ingestion import run_ingestion


def seconds_until_next_run(now: datetime | None = None, hour_utc: int = 2) -> float:
    now = now or datetime.now(timezone.utc)
    target = datetime.combine(now.date(), day_time(hour=hour_utc, tzinfo=timezone.utc))
    if target <= now:
        target += timedelta(days=1)
    return max(0.0, (target - now).total_seconds())


def main() -> None:
    while True:
        time.sleep(seconds_until_next_run())
        try:
            run_ingestion()
        except Exception as exc:
            # Keep details useful without printing connection strings or secrets.
            print(f"Daily ingestion failed: {type(exc).__name__}", flush=True)


if __name__ == "__main__":
    main()
