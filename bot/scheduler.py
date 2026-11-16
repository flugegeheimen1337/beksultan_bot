from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from bot.config import Settings
from bot.db import Database
from bot.reporting import deliver_report

log = logging.getLogger(__name__)


def is_auto_due(last_sent: str | None, today: str, hour: int, now_hour: int) -> bool:
    return now_hour >= hour and last_sent != today


async def auto_report_loop(bot: Bot, db: Database, settings: Settings) -> None:
    while True:
        try:
            await send_due_reports(bot, db, settings)
        except Exception:
            log.exception("auto report loop failed")
        await asyncio.sleep(30)


async def send_due_reports(bot: Bot, db: Database, settings: Settings) -> None:
    zone = settings.zone()
    now = datetime.now(timezone.utc).astimezone(zone)
    today = now.date().isoformat()
    if now.hour < settings.auto_report_hour:
        return
    for chat_id, last_sent in db.auto_chats():
        if not is_auto_due(last_sent, today, settings.auto_report_hour, now.hour):
            continue
        try:
            sent = await deliver_report(
                bot=bot,
                chat_id=chat_id,
                db=db,
                settings=settings,
                start=now.date(),
                end=now.date(),
                message=None,
                reply_markup=None,
            )
        except TelegramForbiddenError:
            db.set_auto(chat_id, False)
            log.info("auto report disabled, bot blocked chat=%s", chat_id)
            continue
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            continue
        except Exception:
            log.exception("auto report failed chat=%s", chat_id)
            continue
        if sent:
            db.mark_auto_sent(chat_id, today)
        await asyncio.sleep(0.05)
