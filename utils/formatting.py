import math
from datetime import datetime


def format_duration(seconds: int, round_up_minutes: bool = True) -> str:
    safe_seconds = max(seconds, 0)
    if round_up_minutes:
        minutes = int(math.ceil(safe_seconds / 60)) if safe_seconds > 0 else 0
    else:
        minutes = safe_seconds // 60
    hours, mins = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def format_week_label(start: datetime, end: datetime) -> str:
    start_label = f"{start.strftime('%b')} {start.day}"
    end_label = f"{end.strftime('%b')} {end.day}"
    return f"{start_label} - {end_label}"


def format_progress_bar(
    current_seconds: int, target_seconds: int, width: int = 20
) -> tuple[str, int]:
    safe_current = max(0, current_seconds)
    safe_target = max(0, target_seconds)
    if safe_target == 0:
        return "[" + ("#" * width) + "]", 100

    ratio = safe_current / safe_target
    clamped_ratio = min(max(ratio, 0.0), 1.0)
    filled = int(round(width * clamped_ratio))
    bar = "[" + ("#" * filled) + ("-" * (width - filled)) + "]"
    percent = int(round(ratio * 100))
    return bar, percent
