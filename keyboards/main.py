from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

START_BTN = "▶️ Start"
END_BTN = "⏹ End"
THIS_WEEK_BTN = "📅 This week"
ALL_STATS_BTN = "📊 All stats"
TARGET_BTN = "🎯 Target"


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=START_BTN), KeyboardButton(text=END_BTN)],
            [KeyboardButton(text=THIS_WEEK_BTN), KeyboardButton(text=ALL_STATS_BTN)],
            [KeyboardButton(text=TARGET_BTN)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
