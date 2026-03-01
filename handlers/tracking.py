from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import Message

from db.connect import Database
from keyboards.main import END_BTN, START_BTN
from utils.formatting import format_duration
from utils.time_utils import compute_week_bounds

router = Router()


@router.message(F.text == START_BTN)
async def start_tracking(message: Message, db: Database) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id
    tz, _ = db.get_user_settings(user_id)
    now_utc = datetime.now(timezone.utc)

    active = db.get_active_session(user_id)
    if active:
        await message.answer(
            "⏱ <b>Session already running</b>\n"
            "Press ⏹ End when you're done."
        )
        return

    db.start_session(user_id, now_utc)
    await message.answer(
        "✅ <b>Tracking started</b>"
    )


@router.message(F.text == END_BTN)
async def end_tracking(message: Message, db: Database) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id
    tz, week_start_day = db.get_user_settings(user_id)
    now_utc = datetime.now(timezone.utc)
    ended = db.end_latest_active_session(user_id, now_utc)
    if not ended:
        await message.answer("No active session. Press ▶️ Start first.")
        return

    session_seconds = ended.duration_seconds or 0

    week_start_utc, week_end_utc = compute_week_bounds(
        now_utc.astimezone(tz), tz=tz, week_start_day=week_start_day
    )
    week_total = db.week_total_seconds(user_id, week_start_utc, week_end_utc)
    await message.answer(
        "🛑 <b>Session ended</b>\n"
        f"Session: <b>{format_duration(session_seconds)}</b>\n"
        f"This week total: <b>{format_duration(week_total)}</b>."
    )
