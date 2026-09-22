# Daily scan behavior and macOS automation

## Verified current behavior

The project uses **manual scans**. `src/main.py` invokes `run_scan` only when the scan command runs. The pipeline contains no timer, launch agent, cron integration, or background scheduling loop. Starting the dashboard only starts a local read-only HTTP server.

`Storage.start_run` inserts a new `runs` row each time. Filter observations and consolidated results reference that run ID. Finishing a run updates only that run's status and appends its consolidated results; it does not delete old dates. JSON exports are also separated by date and run ID. The optional `latest-scan.json` export can be replaced because it is a convenience copy, not the history store.

For a date with several attempts, the dashboard prefers its most recent complete run. If there is no complete run, it may show a clearly labeled partial snapshot. Historical ticker charts use the latest complete run on each of up to seven collected dates. The original CLI still queries seven calendar days.

## Options

| Option | Fit for this project | Limitation |
|---|---|---|
| macOS user LaunchAgent | Recommended: runs the existing virtualenv Python command, without keeping the dashboard open | User session and network must be available; schedule uses the Mac's local time |
| cron | Simple for a machine that stays awake | Scheduled invocations are skipped while the Mac sleeps |
| Python scheduler process | Possible, but adds dependencies or a persistent process | Must itself be supervised and restarted, duplicating operating-system functionality |

Apple documents `StartCalendarInterval` for timed launchd jobs. A job missed during sleep runs after waking; a powered-off Mac does not recover a missed invocation in the same way. See [Apple: Scheduling Timed Jobs](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html).

## Recommended implementation, when authorized

Create a user LaunchAgent with these values:

- Label: `local.finviz-filter-tracker.scan`.
- `ProgramArguments`: absolute path to this repository's `.venv/bin/python`, followed by `-m`, `src.main`, `scan`, `--output`, and an absolute `data/latest-scan.json` path.
- `WorkingDirectory`: this repository's absolute path.
- `StartCalendarInterval`: the chosen local hour and minute, optionally a weekday restriction.
- `StandardOutPath` and `StandardErrorPath`: separate files in `data/logs/`.
- No `KeepAlive`: a failed scan should not trigger an uncontrolled retry loop.

Before enabling it, choose the desired scan time and align the Mac's scheduling timezone with the scan's `--timezone` value. Add bounded retries for incomplete scans, a lock to avoid overlap with manual runs, and a simple notification on persistent failure. Keep holiday behavior explicit; the current backend does not implement a market calendar.

When the Mac wakes late, the scraper records what Finviz returns at that actual time. It cannot reconstruct a missed day's results. The schedule therefore improves collection consistency but cannot guarantee a daily observation if the computer is off or offline.

No plist, cron entry, or system-level scheduler has been installed as part of the frontend work. The existing manual command remains the operational path:

```bash
cd /Users/diegovillanuevafernandez/finviz-filter-tracker
.venv/bin/python -m src.main scan --output data/latest-scan.json
```
