from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from db.connect import Database
from keyboards.main import TARGET_BTN, get_main_keyboard
from utils.formatting import format_duration

router = Router()


@router.message(CommandStart())
async def start_command(message: Message, db: Database) -> None:
    if not message.from_user:
        return
    db.ensure_user(message.from_user.id)
    await message.answer(
        "✅ <b>Time tracker is ready</b>\n\n"
        "Use the buttons:\n"
        "▶️ Start - begin a session\n"
        "⏹ End - finish active session\n"
        "📅 This week - totals and progress\n"
        "📊 All stats - all-time and weekly history\n"
        "🎯 Target - view your weekly goal\n\n"
        "Set target with <code>/target 30</code> (hours).\n"
        "Set timezone with <code>/timezone Asia/Tashkent</code>.",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("target"))
async def target_command(message: Message, db: Database) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 1:
        current_target = db.get_week_target_seconds(user_id)
        await message.answer(
            f"🎯 <b>Weekly target:</b> {format_duration(current_target)}\n"
            "Change it with <code>/target 30</code> or <code>/target 37.5</code>."
        )
        return

    raw_value = parts[1].strip().replace(",", ".")
    try:
        hours = float(raw_value)
    except ValueError:
        await message.answer("Invalid format. Example: <code>/target 30</code>")
        return

    if hours <= 0 or hours > 168:
        await message.answer(
            "Target must be between 0 and 168 hours.\n"
            "Example: <code>/target 30</code>"
        )
        return

    target_seconds = int(hours * 3600)
    db.set_week_target_seconds(user_id, target_seconds)
    await message.answer(
        f"✅ <b>Weekly target updated:</b> {format_duration(target_seconds)}\n"
        "Open 📅 This week to see progress."
    )


@router.message(Command("timezone"))
async def timezone_command(message: Message, db: Database) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) == 1:
        tz_name = db.get_user_timezone_name(user_id)
        await message.answer(
            f"🕒 <b>Your timezone:</b> <code>{tz_name}</code>\n"
            "Set with <code>/timezone Region/City</code>\n"
            "Example: <code>/timezone Asia/Tashkent</code>"
        )
        return

    tz_name = parts[1].strip()
    if not tz_name:
        await message.answer("Invalid format. Example: <code>/timezone Asia/Tashkent</code>")
        return

    if not db.set_user_timezone(user_id, tz_name):
        await message.answer(
            "Timezone not found.\n"
            "Use IANA format like <code>Europe/Berlin</code> or <code>Asia/Tashkent</code>."
        )
        return

    await message.answer(
        f"✅ <b>Timezone updated:</b> <code>{tz_name}</code>\n"
        "New session times and week boundaries now use this timezone."
    )


@router.message(F.text == TARGET_BTN)
async def target_button(message: Message, db: Database) -> None:
    if not message.from_user:
        return
    current_target = db.get_week_target_seconds(message.from_user.id)
    await message.answer(
        f"🎯 <b>Weekly target:</b> {format_duration(current_target)}\n"
        "Change it with <code>/target &lt;hours&gt;</code>, for example <code>/target 30</code>."
    )
