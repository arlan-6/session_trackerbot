from datetime import date, datetime, timedelta, timezone
from collections import defaultdict

from aiogram import F, Router
from aiogram.types import Message

from db.connect import Database
from keyboards.main import ALL_STATS_BTN, THIS_WEEK_BTN
from utils.formatting import format_duration, format_progress_bar, format_week_label
from utils.time_utils import compute_week_bounds

router = Router()


@router.message(F.text == THIS_WEEK_BTN)
async def show_this_week(message: Message, db: Database) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id
    tz, week_start_day = db.get_user_settings(user_id)
    now_local = datetime.now(timezone.utc).astimezone(tz)
    week_start_utc, week_end_utc = compute_week_bounds(
        now_local, tz=tz, week_start_day=week_start_day
    )

    total_seconds = db.week_total_seconds(user_id, week_start_utc, week_end_utc)
    target_seconds = db.get_week_target_seconds(user_id)
    sessions = db.recent_sessions_for_week(user_id, week_start_utc, week_end_utc, limit=5)
    week_label = format_week_label(
        week_start_utc.astimezone(tz), (week_end_utc - timedelta(seconds=1)).astimezone(tz)
    )
    progress_bar, progress_percent = format_progress_bar(total_seconds, target_seconds)

    lines = [
        f"📅 <b>This week</b> ({week_label})\n",
        f"Tracked: <b>{format_duration(total_seconds)}</b>",
        f"Target: <b>{format_duration(target_seconds)}</b>",
        f"\nProgress: <code>{progress_bar}</code> <b>{progress_percent}%</b>",
    ]

    if sessions:
        daily_totals: dict[date, int] = defaultdict(int)
        for session in sessions:
            local_start = session.start_time.astimezone(tz)
            daily_totals[local_start.date()] += session.duration_seconds or 0
        lines.append("\nBy dates:")
        for date_value, day_total in sorted(daily_totals.items()):
            date_label = date_value.strftime("%a, %b %d")
            lines.append(f"• {date_label}: {format_duration(day_total)}")
    else:
        lines.append("No completed sessions this week yet.")

    await message.answer("\n".join(lines))


@router.message(F.text == ALL_STATS_BTN)
async def show_all_stats(message: Message, db: Database) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id

    all_time = db.all_time_total_seconds(user_id)
    stats = db.weekly_stats(user_id, limit_weeks=8)
    breakdown = stats["breakdown"]
    best_week = stats["best_week"]
    average_seconds = stats["average_seconds"]

    lines = [f"📊 <b>All stats</b>\n", f"All-time total: <b>{format_duration(all_time)}</b>"]
    if breakdown:
        lines.append("By weeks:")
        for week_start_local, total in breakdown:
            week_end_local = week_start_local + timedelta(days=7) - timedelta(seconds=1)
            lines.append(f"• {format_week_label(week_start_local, week_end_local)}: {format_duration(total)}")
        if best_week:
            best_start, best_total = best_week
            best_end = best_start + timedelta(days=7) - timedelta(seconds=1)
            lines.append(
                f"\n🏆 Best week: {format_week_label(best_start, best_end)} ({format_duration(best_total)})"
            )
        lines.append(f"\n📈 Average per week: {format_duration(average_seconds)}")
    else:
        lines.append("No completed sessions yet.")

    await message.answer("\n".join(lines))
