import argparse
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from redminelib import Redmine  # type: ignore[import-untyped]

from logtime.config import api_key, defaults, redmine_url, root_folder

LOG_TZ = ZoneInfo("Europe/Prague")

NUMBER_TO_DAY_OF_WEEK = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}

EIGHT_HOURS_IN_MINS = 8 * 60

logger = logging.getLogger(__name__)


Lines = list[str]
Grouped = dict[str, dict[str, Any]]


@dataclass
class TaskResult:
    task_id: str | None
    delta_seconds: int
    desc: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process logtime arguments")
    parser.add_argument("--days-back", type=int, help="Number of days to go back", default=0)
    return parser.parse_args()


# Compiled once and reused by parsing helpers below
LINE_PATTERN = re.compile(r"^(\s*\d{1,2}:\d{2})\s+([0-9]{5})?\s*(.*)$")


def parse_line(line: str) -> tuple[str, str | None, str] | None:
    """Parse a single line into (time_str, task_id, desc) or return None when it doesn't match.

    The returned time_str is stripped of whitespace and in the format 'HH:MM'.
    """
    m = LINE_PATTERN.match(line)
    if not m:
        return None
    time_str = m.group(1).strip()
    task_id = m.group(2)
    desc = m.group(3) or ""
    return time_str, task_id, desc


class SetEncoder(json.JSONEncoder):
    def default(self, o: object) -> object:  # match base signature
        if isinstance(o, set):
            return list(o)
        return super().default(o)


def get_path(today: datetime) -> Path:
    """Return the expected markdown file Path for given date.

    Example: <root_folder>/2026/02/2026-02-21 MO.md
    """
    year = today.year
    month = f"{today.month:02d}"
    whole_date = today.strftime("%Y-%m-%d")
    day_of_the_week = NUMBER_TO_DAY_OF_WEEK[today.weekday()]
    file_path = Path(root_folder) / str(year) / month / f"{whole_date} {day_of_the_week}.md"
    return file_path.expanduser()


def get_lines(path: Path) -> Lines:
    """Read non-empty lines from file and return as a list without trailing newlines."""
    if not path.exists():
        logger.error("Log file not found: %s", path)
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as fh:
        # strip only trailing newline; ignore purely-empty lines
        return [line.rstrip("\n") for line in fh if line.strip()]


def is_already_parsed(lines: Lines) -> bool:
    """Return True when file contains a trailing marker that indicates it's already processed."""
    if not lines:
        return False
    is_parsed = lines[-1].strip() == "already parsed"
    if is_parsed:
        logger.info("File already parsed")
    return is_parsed


def get_timestamps(today: datetime, lines: Iterable[str]) -> list[datetime]:
    """Parse timestamps (HH:MM) from the start of lines and return datetime objects with LOG_TZ.

    Uses :func:`parse_line` so the same line-format validation is shared with task parsing.
    """
    timestamps: list[datetime] = []
    for line in lines:
        parsed = parse_line(line)
        if not parsed:
            # not a timestamp at start of line (or unrecognized format)
            continue
        time_str, _, _ = parsed
        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError:
            continue
        timestamps.append(
            datetime(
                year=today.year,
                month=today.month,
                day=today.day,
                hour=hour,
                minute=minute,
                tzinfo=LOG_TZ,
            ),
        )
    return timestamps


def get_deltas(timestamps: list[datetime]) -> list[timedelta]:
    """Return a list of timedeltas between consecutive timestamps."""
    return [j - i for i, j in pairwise(timestamps)] if len(timestamps) > 1 else []


def get_tasks_results(deltas: list[timedelta], lines: Lines) -> list[TaskResult]:
    """Parse each line and pair with the corresponding delta to produce TaskResult objects.

    Expected line example: "08:00 12345 Some description"
    Task id is optional; lines that don't match the expected pattern are skipped.
    """
    results: list[TaskResult] = []
    for i, line in enumerate(lines):
        parsed = parse_line(line)
        if not parsed:
            logger.warning("Unrecognized line format (skipping): %s", line)
            continue
        _, task_id, desc = parsed
        if i >= len(deltas):
            # last timestamp has no following delta
            break
        delta_seconds = int(deltas[i].total_seconds())
        results.append(TaskResult(task_id=task_id, delta_seconds=delta_seconds, desc=desc))
    return results


def group_tasks(tasks_results: list[TaskResult]) -> Grouped:
    """Aggregate TaskResult items by (task id + desc) or by description when no task id.

    Returns a mapping from grouping key to aggregated info including minutes and rounded hours.
    """
    grouped: Grouped = {}
    for tr in tasks_results:
        mins = int(tr.delta_seconds / 60)
        if tr.task_id:
            key = f"{tr.task_id} {tr.desc}"
            entry = grouped.setdefault(key, {"delta": 0, "desc": set(), "task_id": tr.task_id})
        else:
            key = tr.desc or "#no-desc"
            entry = grouped.setdefault(key, {"delta": 0, "desc": set()})
        entry["delta"] += mins
        if tr.desc:
            entry["desc"].add(tr.desc)

    # finalize computed fields
    for values in grouped.values():
        total_mins = int(values["delta"])
        values["task_total_mins"] = total_mins
        values["task_total_hours"] = total_mins // 60
        values["task_total_rest"] = total_mins % 60
        values["rounded_hours"] = minutes_to_rounded_decimal_hours(total_mins)
    return grouped


def minutes_to_rounded_decimal_hours(total_minutes: int) -> float:
    """Convert minutes to decimal hours rounded to the nearest quarter hour (0.25)."""
    hours = total_minutes / 60.0
    return round(hours * 4) / 4


def append_result(
    path: Path,
    grouped_tasks: Grouped,
    total_delta_work: int,
    total_delta_free: int,
) -> None:
    """Append a human-readable summary to the end of the log file.

    `total_delta_work` and `total_delta_free` are in seconds.
    """
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n\nSummary:\n")
        total_rounded_hours = 0.0
        for task, values in grouped_tasks.items():
            # accumulate only real tasks (not special '#'-prefixed groups)
            if not task.startswith("#"):
                total_rounded_hours += float(values.get("rounded_hours", 0))
            joined_desc = ", ".join(sorted(values.get("desc", [])))

            if not task.startswith("#"):
                # prefer showing task id before descriptions when meaningful
                text = (
                    joined_desc
                    if values.get("task_id") is None or joined_desc == values.get("task_id")
                    else f"{values.get('task_id')} {joined_desc}"
                )
            else:
                text = joined_desc if joined_desc == task else f"{task} {joined_desc}"

            fh.write(
                f"{values['task_total_mins']} = {values['task_total_hours']}h "
                f"{values['task_total_rest']}m ~ {values['rounded_hours']}h: {text}\n",
            )

        fh.write("\n")
        # Convert seconds to minutes for totals
        total_mins = int((total_delta_work + total_delta_free) / 60)
        total_hours = total_mins // 60
        total_rest = total_mins % 60

        total_delta_work_mins = int(total_delta_work / 60)
        total_delta_free_mins = int(total_delta_free / 60)

        total_delta_work_hours = total_delta_work_mins // 60
        total_delta_free_hours = total_delta_free_mins // 60

        total_delta_work_rest = total_delta_work_mins % 60
        total_delta_free_rest = total_delta_free_mins % 60

        saldo_mins = int(abs(total_rounded_hours * 60 - EIGHT_HOURS_IN_MINS))
        is_saldo_ge_zero = total_delta_work_mins >= EIGHT_HOURS_IN_MINS
        saldo_hours = saldo_mins // 60
        saldo_rest = saldo_mins % 60
        sign = "" if is_saldo_ge_zero else "-"

        fh.write(f"total: {total_hours}h {total_rest}m ({total_mins})\n")
        fh.write(
            f"total work: {total_delta_work_hours}h {total_delta_work_rest}m "
            f"({total_delta_work_mins})\n",
        )
        fh.write(f"total work rounded hours: {total_rounded_hours}\n")
        fh.write(
            f"total free:  {total_delta_free_hours}h {total_delta_free_rest}m "
            f"({total_delta_free_mins})\n",
        )
        fh.write(f"saldo: {sign}{saldo_hours}h {saldo_rest}m ({sign}{saldo_mins})\n")
        if saldo_mins == 0:
            fh.write("working šul-nul\n")
        elif sign == "":
            fh.write("working too much\n")
        else:
            fh.write("working too little\n")
        fh.write("already parsed")


def apply_defaults(grouped_tasks: Grouped, defaults_map: dict[str, str]) -> None:
    """Apply default task ids from the provided mapping.

    This mutates `grouped_tasks` in-place.
    """
    for description, value in defaults_map.items():
        if description in grouped_tasks:
            grouped_tasks[description]["task_id"] = value


def compute_totals(tasks_results: list[TaskResult]) -> tuple[int, int]:
    """Return (total_delta_work_seconds, total_delta_free_seconds)."""
    total_delta_work = sum(tr.delta_seconds for tr in tasks_results if not tr.desc.startswith("#"))
    total_delta_free = sum(tr.delta_seconds for tr in tasks_results if tr.desc.startswith("#"))
    return total_delta_work, total_delta_free


def create_redmine_client() -> Redmine:
    return Redmine(
        redmine_url,
        key=api_key,
    )


def send_time_entries(grouped_tasks: Grouped, redmine_client: Redmine, date: datetime) -> None:
    """Send rounded time entries for grouped tasks to Redmine.

    Only tasks that have a `task_id` and positive `rounded_hours` are sent.
    """
    result_date = date.strftime("%Y-%m-%d")
    for grouped_task in grouped_tasks.values():
        task_id = grouped_task.get("task_id")
        if task_id and grouped_task.get("rounded_hours", 0) > 0:
            desc_text = ", ".join(sorted(grouped_task.get("desc", [])))
            hours = float(grouped_task["rounded_hours"])
            redmine_client.time_entry.create(
                issue_id=task_id,
                spent_on=result_date,
                hours=hours,
                comments=desc_text,
            )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    days_back = int(args.days_back)
    today = datetime.now(LOG_TZ) - timedelta(days=days_back)
    path = get_path(today=today)

    lines = get_lines(path)
    if is_already_parsed(lines):
        return

    timestamps = get_timestamps(today, lines)
    deltas = get_deltas(timestamps)
    tasks_results = get_tasks_results(deltas, lines)

    total_delta_work, total_delta_free = compute_totals(tasks_results)

    grouped_tasks = group_tasks(tasks_results)
    apply_defaults(grouped_tasks, defaults)
    append_result(path, grouped_tasks, total_delta_work, total_delta_free)

    logger.info(json.dumps(grouped_tasks, indent=4, cls=SetEncoder))

    answer = input("Send on api? (y/n): ")
    if answer.strip().lower() != "y":
        logger.info("User declined sending to API. Finishing.")
        return

    redmine = create_redmine_client()
    send_time_entries(grouped_tasks, redmine, today)


if __name__ == "__main__":
    main()
