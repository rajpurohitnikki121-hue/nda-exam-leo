"""Owner / admin commands (only users listed in ADMIN_IDS can use them).

/users      - total users, new today, latest 15 users
/userlist   - full list of users as a .csv file
/botstats   - users, NDA tests since last restart, question bank
"""

import csv
import html
import io
import logging
from datetime import datetime, timedelta

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from sqlalchemy import func, select

from config import settings
from database.connection import get_db
from database.models import User
from services.nda_bank import bank

logger = logging.getLogger(__name__)
router = Router(name="owner_router")

IST = timedelta(hours=5, minutes=30)


def _ist(dt: datetime) -> str:
    return (dt + IST).strftime("%d %b %H:%M")


async def _guard(message: types.Message) -> bool:
    user = message.from_user
    if not user or not settings.is_admin(user.id):
        await message.answer(
            "⛔ Ye command sirf owner/admin ke liye hai.\n"
            f"Tumhari Telegram ID: <code>{user.id if user else '?'}</code>"
        )
        return False
    return True


@router.message(Command("users"))
async def cmd_users(message: types.Message) -> None:
    if not await _guard(message):
        return
    now = datetime.utcnow()
    async with get_db() as session:
        total = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        new_24h = (
            await session.execute(
                select(func.count()).select_from(User).where(User.created_at >= now - timedelta(hours=24))
            )
        ).scalar_one()
        active_24h = (
            await session.execute(
                select(func.count()).select_from(User).where(User.updated_at >= now - timedelta(hours=24))
            )
        ).scalar_one()
        latest = list(
            (await session.execute(select(User).order_by(User.created_at.desc()).limit(15))).scalars().all()
        )

    lines = [
        "👥 <b>Bot Users</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"Total users: <b>{total}</b>",
        f"Naye (24 ghante): <b>{new_24h}</b>",
        f"Active (24 ghante): <b>{active_24h}</b>",
        "",
        "<b>Latest 15 users:</b>",
    ]
    for u in latest:
        uname = f"@{html.escape(u.username)}" if u.username else "—"
        lines.append(
            f"• {html.escape(u.full_name or 'Unknown')} · {uname} · <code>{u.user_id}</code> · {_ist(u.created_at)}"
        )
    lines.append("\n<i>Poori list ke liye /userlist (CSV file). Time IST me hai.</i>")
    await message.answer("\n".join(lines))


@router.message(Command("userlist"))
async def cmd_userlist(message: types.Message) -> None:
    if not await _guard(message):
        return
    async with get_db() as session:
        rows = list((await session.execute(select(User).order_by(User.created_at))).scalars().all())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "username", "full_name", "joined_utc", "last_seen_utc"])
    for u in rows:
        w.writerow([u.user_id, u.username or "", u.full_name or "", u.created_at, u.updated_at])
    data = buf.getvalue().encode("utf-8-sig")
    await message.answer_document(
        BufferedInputFile(data, filename="users.csv"), caption=f"👥 {len(rows)} users"
    )


@router.message(Command("botstats"))
async def cmd_botstats(message: types.Message) -> None:
    if not await _guard(message):
        return
    from handlers import nda_exam  # local import avoids circular import at startup

    async with get_db() as session:
        total = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    counts = bank.counts()
    st = nda_exam.STATS
    await message.answer(
        "📊 <b>Bot Stats</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total users: <b>{total}</b>\n"
        f"📚 Question bank: Maths <b>{counts['maths']}</b> · GAT <b>{counts['gat']}</b>\n\n"
        "<b>NDA tests (last restart ke baad):</b>\n"
        f"🚀 Started: <b>{st['started']}</b>\n"
        f"🏁 Finished: <b>{st['finished']}</b>\n"
        f"🟢 Abhi chal rahe: <b>{len(nda_exam.ACTIVE)}</b>"
    )
