"""Force-subscribe: users must be members of settings.FORCE_SUB_CHANNEL to use the bot.

NOTE: the bot must be an ADMIN of that channel, otherwise Telegram does not let it
check who is a member. If the check is impossible we let users through (and log a
warning) instead of locking everybody out.
"""

import html
import logging
import time
from typing import Dict, Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from keyboards.callbacks import FsubCB

logger = logging.getLogger(__name__)

MEMBER_CACHE_S = 120
_member_until: Dict[int, float] = {}
_last_warn = 0.0


async def check_membership(bot: Bot, user_id: int, fresh: bool = False) -> Optional[bool]:
    """True = member, False = not a member, None = could not check (treated as allowed)."""
    global _last_warn
    chat = settings.force_sub_chat
    if chat is None:
        return True
    now = time.monotonic()
    if not fresh and _member_until.get(user_id, 0) > now:
        return True
    try:
        member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
    except Exception as exc:
        if now - _last_warn > 600:
            _last_warn = now
            logger.warning(
                "FORCE-SUB check failed for %s: %s  -> Bot ko channel me ADMIN banao! "
                "(jab tak check nahi ho sakta, sab users allowed hain)",
                chat,
                exc,
            )
        return None
    status = getattr(member, "status", "")
    if status in ("member", "administrator", "creator"):
        ok = True
    elif status == "restricted":
        ok = bool(getattr(member, "is_member", False))
    else:  # left / kicked
        ok = False
    if ok:
        _member_until[user_id] = now + MEMBER_CACHE_S
    else:
        _member_until.pop(user_id, None)
    return ok


def join_text(name: str) -> str:
    return (
        "🔗 <b>CHANNEL JOIN REQUIRED</b>\n\n"
        f"👋 Hi <b>{html.escape(name)}</b>!\n\n"
        "Bot use karne ke liye pehle neeche wala channel join karo, "
        "phir <b>✅ CHECK MEMBERSHIP</b> dabao."
    )


def join_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    url = settings.force_sub_url
    if url:
        b.row(InlineKeyboardButton(text="📢 JOIN CHANNEL", url=url))
    b.row(InlineKeyboardButton(text="✅ CHECK MEMBERSHIP", callback_data=FsubCB(a="check").pack()))
    return b.as_markup()
