from datetime import datetime

import logtime.logtime as lt


def test_parse_line_full() -> None:
    line = "08:00 12345 Fix bug"
    parsed = lt.parse_line(line)
    assert parsed == ("08:00", "12345", "Fix bug")


def test_parse_line_no_task() -> None:
    line = "09:15 Some note"
    parsed = lt.parse_line(line)
    assert parsed == ("09:15", None, "Some note")


def test_get_timestamps_and_deltas() -> None:
    today = datetime(2026, 2, 21, tzinfo=lt.LOG_TZ)
    lines = ["08:00 start", "09:30 end"]
    timestamps = lt.get_timestamps(today, lines)
    assert len(timestamps) == 2
    assert timestamps[0].hour == 8
    assert timestamps[0].minute == 0
    # deltas
    deltas = lt.get_deltas(timestamps)
    assert len(deltas) == 1
    assert int(deltas[0].total_seconds()) == 90 * 60


def test_get_tasks_results() -> None:
    today = datetime(2026, 2, 21, tzinfo=lt.LOG_TZ)
    lines = ["08:00 12345 Task A", "09:00 12345 Task A"]
    timestamps = lt.get_timestamps(today, lines)
    deltas = lt.get_deltas(timestamps)
    results = lt.get_tasks_results(deltas, lines)
    assert len(results) == 1
    tr = results[0]
    assert tr.task_id == "12345"
    assert tr.desc == "Task A"
    assert tr.delta_seconds == 3600


def test_minutes_to_rounded_decimal_hours() -> None:
    assert lt.minutes_to_rounded_decimal_hours(0) == 0
    assert lt.minutes_to_rounded_decimal_hours(15) == 0.25
    assert lt.minutes_to_rounded_decimal_hours(30) == 0.5
    assert lt.minutes_to_rounded_decimal_hours(45) == 0.75
    assert lt.minutes_to_rounded_decimal_hours(60) == 1.0
