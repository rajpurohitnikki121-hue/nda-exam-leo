"""Tracks every user who talks to the bot: saves them in the DB and writes log lines.

Log lines you will see in the console:
  👤 NEW USER   - first time this person ever used the bot
  ⌨️  COMMAND    - every /command someone sends
"""

import html
import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from database.connection import get_db
from config import settings
from database.models import User
from services import force_sub
from services.stats_service import StatsService

logger = logging.getLogger("users")

TOUCH_EVERY_S = 300  # refresh "last seen" in DB at most once per 5 minutes per user
_last_touch: Dict[int, float] = {}


def user_label(user) -> str:
    uname = f"@{user.username}" if getattr(user, "username", None) else "no-username"
    return f"{user.full_name} ({uname}, id={user.id})"


class TrackUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is not None and not user.is_bot:
            try:
                if isinstance(event, Message) and event.text and event.text.startswith("/"):
                    logger.info("⌨️  COMMAND %s from %s", event.text.split()[0], user_label(user))
                await self._track(user)
            except Exception:  # tracking must never break the bot
                logger.exception("user tracking failed")
        return await handler(event, data)

    @staticmethod
    async def _track(user) -> None:
        now = time.monotonic()
        last = _last_touch.get(user.id)
        if last is not None and now - last < TOUCH_EVERY_S:
            return
        _last_touch[user.id] = now

        async with get_db() as session:
            existing = await session.get(User, user.id)
            row = await StatsService.get_or_create_user(
                session=session,
                user_id=user.id,
                username=user.username,
                full_name=user.full_name,
            )
            from datetime import datetime

            row.updated_at = datetime.utcnow()
            if existing is None:
                logger.info("👤 NEW USER %s", user_label(user))


class ForceSubMiddleware(BaseMiddleware):
    """Blocks everything (except the CHECK MEMBERSHIP button) until the user joined the channel."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if settings.force_sub_chat is None or user is None or user.is_bot or settings.is_admin(user.id):
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            if event.data and event.data.startswith("fs:"):
                return await handler(event, data)
            chat = event.message.chat if event.message else None
        elif isinstance(event, Message):
            chat = event.chat
        else:
            return await handler(event, data)
        if chat is not None and chat.type != "private":
            return await handler(event, data)

        ok = await force_sub.check_membership(data["bot"], user.id)
        if ok is not False:  # member, or check impossible (fail-open)
            return await handler(event, data)

        logger.info("🔒 FORCE-SUB blocked %s", user_label(user))
        target = event.message if isinstance(event, CallbackQuery) else event
        if isinstance(event, CallbackQuery):
            await event.answer("Pehle channel join karo 👇", show_alert=True)
        await target.answer(force_sub.join_text(user.full_name), reply_markup=force_sub.join_kb())
        return None
