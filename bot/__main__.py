from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from bot.config import load_settings, setup_logging
from bot.db import Database
from bot.handlers import register
from bot.scheduler import auto_report_loop
from bot.texts import DESCRIPTION, SHORT_DESCRIPTION

log = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="help", description="Что умеет бот"),
    BotCommand(command="report", description="Собрать отчёт"),
    BotCommand(command="balance", description="Наличные и карта"),
    BotCommand(command="debts", description="Книга должников"),
    BotCommand(command="edit", description="Изменить или удалить запись"),
    BotCommand(command="cancel", description="Отменить действие"),
]


async def setup_profile(bot: Bot) -> None:
    me = await bot.get_me()
    log.info("started as @%s", me.username)
    await bot.delete_webhook(drop_pending_updates=False)
    log.info("webhook deleted")
    try:
        await bot.set_my_commands(COMMANDS)
        await bot.set_my_commands(COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(COMMANDS, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_description(DESCRIPTION)
        await bot.set_my_short_description(SHORT_DESCRIPTION)
    except Exception:
        log.exception("failed to update bot profile")


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.bot_token)
    database = Database(settings.db_path)
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(
        storage=MemoryStorage(),
        events_isolation=SimpleEventIsolation(),
    )
    register(dispatcher)
    await setup_profile(bot)
    log.info(
        "timezone=%s auto_report_hour=%s",
        settings.timezone,
        settings.auto_report_hour,
    )
    task = asyncio.create_task(auto_report_loop(bot, database, settings))
    try:
        await dispatcher.start_polling(bot, db=database, settings=settings)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
