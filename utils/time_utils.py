from datetime import datetime, time, timedelta, timezone, tzinfo


def format_local_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def compute_week_bounds(
    now_local: datetime, tz: tzinfo, week_start_day: int = 0
) -> tuple[datetime, datetime]:
    week_start_day = week_start_day % 7
    now_local = now_local.astimezone(tz)
    current_weekday = now_local.weekday()
    offset_days = (current_weekday - week_start_day) % 7
    week_start_date = (now_local - timedelta(days=offset_days)).date()
    week_start_local = datetime.combine(week_start_date, time.min, tzinfo=tz)
    week_end_local = week_start_local + timedelta(days=7)
    return week_start_local.astimezone(timezone.utc), week_end_local.astimezone(
        timezone.utc
    )
