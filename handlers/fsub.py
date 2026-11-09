"""Force-subscribe: CHECK MEMBERSHIP button and /fsub status command for admins."""

import logging

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import settings
from keyboards.callbacks import FsubCB, NdaCB
from services import force_sub

logger = logging.getLogger(__name__)
router = Router(name="fsub_router")


@router.callback_query(FsubCB.filter(F.a == "check"))
async def cb_check(cb: types.CallbackQuery, bot: Bot) -> None:
    ok = await force_sub.check_membership(bot, cb.from_user.id, fresh=True)
    if ok is False:
        await cb.answer("❌ Abhi tak channel join nahi kiya. Pehle JOIN dabao, phir dobara check karo.", show_alert=True)
        return
    await cb.answer("✅ Verified!")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🎖️ NDA Exam Practice", callback_data=NdaCB(a="home").pack()))
    try:
        await cb.message.edit_text(
            "✅ <b>Membership verified!</b>\n\nAb bot use kar sakte ho. /nda dabao ya neeche button dabao.",
            reply_markup=b.as_markup(),
        )
    except Exception:
        await cb.message.answer("✅ Membership verified! /nda dabao.")


@router.message(Command("fsub"))
async def cmd_fsub(message: types.Message, bot: Bot) -> None:
    if not message.from_user or not settings.is_admin(message.from_user.id):
        return
    chat = settings.force_sub_chat
    if chat is None:
        await message.answer("🔓 Force-sub band hai (FORCE_SUB_CHANNEL khali hai).")
        return
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id=chat, user_id=me.id)
        if member.status in ("administrator", "creator"):
            await message.answer(f"✅ Force-sub chal raha hai.\nChannel: <code>{chat}</code>\nBot channel me <b>admin</b> hai.")
        else:
            await message.answer(
                f"⚠️ Bot channel <code>{chat}</code> me hai par admin nahi (status: {member.status}).\n"
                "Bot ko channel me <b>Admin</b> banao, warna membership check nahi hoga."
            )
    except Exception as exc:
        await message.answer(
            f"❌ Channel <code>{chat}</code> check nahi ho paya:\n<code>{exc}</code>\n\n"
            "Bot ko us channel me <b>Admin</b> banao (koi special permission nahi chahiye), "
            "aur FORCE_SUB_CHANNEL sahi hai ya nahi dekho."
        )
