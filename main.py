import asyncio
import logging
import os
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from db.connect import Database
from handlers.menu import router as menu_router
from handlers.stats import router as stats_router
from handlers.tracking import router as tracking_router


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Environment variable {name} is required. "
            f"Set it in OS env or in .env file."
        )
    return value


@dataclass(frozen=True)
class Settings:
    bot_token: str
    db_path: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        bot_token=get_required_env("BOT_TOKEN"),
        db_path=os.getenv("DB_PATH", "week_hours.db"),
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()

    db = Database(settings.db_path)
    db.init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp["db"] = db

    dp.include_router(menu_router)
    dp.include_router(tracking_router)
    dp.include_router(stats_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
