import html
from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from config import settings
from database.connection import get_db
from keyboards.callbacks import NavCB
from keyboards.inline_builders import build_exam_kb, build_main_menu_kb
from services.stats_service import StatsService

router = Router(name="start_router")


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """Handle /start command with user registration and welcome interface."""
    await state.clear()
    user = message.from_user
    if not user:
        return

    # Register/update user in database
    async with get_db() as session:
        await StatsService.get_or_create_user(
            session=session,
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
        )

    is_admin = settings.is_admin(user.id)
    welcome_text = (
        f"🎖️ <b>NDA Exam Practice Bot</b> 🇮🇳\n"
        f"<i>National Defence Academy exam ki practice, real exam style me.</i>\n\n"
        f"Hello <b>{html.escape(user.first_name)}</b>! 🎯\n\n"
        f"⚡ <b>Kya milega:</b>\n"
        f"✅ <b>Maths</b> (120 Q) aur <b>GAT</b> (150 Q) papers\n"
        f"✅ Custom test (10/25/50 Q) ya <b>Full NDA paper</b> with timer\n"
        f"✅ NDA <b>negative marking</b> (ON/OFF option)\n"
        f"✅ End me score, accuracy aur galat questions ka review\n\n"
        f"👇 <i>/nda dabao ya neeche button se test shuru karo:</i>"
    )

    await message.answer(
        text=welcome_text,
        reply_markup=build_main_menu_kb(is_admin=is_admin),
        parse_mode="HTML",
    )


@router.message(Command("menu"))
async def cmd_menu(message: types.Message, state: FSMContext) -> None:
    """Handle /menu command to display main dashboard."""
    await state.clear()
    is_admin = settings.is_admin(message.from_user.id) if message.from_user else False
    await message.answer(
        text="🏠 <b>Main Menu Dashboard</b>\n<i>Choose a practice module or view your progress:</i>",
        reply_markup=build_main_menu_kb(is_admin=is_admin),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    """Handle /help command with complete instructions and command manual."""
    help_text = (
        "📖 <b>NDA Exam Practice Bot — Guide</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎮 <b>Test kaise doge:</b>\n"
        "1. /nda dabao ya menu me <b>🎖️ NDA Exam Practice</b> chuno\n"
        "2. Paper chuno: <b>Maths</b>, <b>GAT</b> ya <b>Mixed</b>\n"
        "3. Questions chuno: <b>10 / 25 / 50</b> ya <b>Full NDA paper</b> (timer ke saath)\n"
        "4. <b>Negative marking ON/OFF</b> chuno\n"
        "5. A/B/C/D dabao. Prev, Skip, Clear aur Submit buttons use karo\n"
        "6. End me score, accuracy aur galat questions ka review milega\n\n"
        "📌 <b>Commands:</b>\n"
        "• /start — Welcome screen\n"
        "• /nda — NDA test shuru karo\n"
        "• /menu — Main menu\n"
        "• /stats — Performance\n"
        "• /leaderboard — Leaderboard\n"
        "• /cancel — Current flow cancel\n"
        "• /help — Ye guide\n\n"
    )

    if message.from_user and settings.is_admin(message.from_user.id):
        help_text += (
            f"👑 <b>Admin Commands:</b>\n"
            f"• /broadcast_quiz — Broadcast interactive Quiz Polls to Channel\n"
            f"• /admin — Open Admin Control Center\n\n"
        )

    help_text += f"📢 <b>Connected Channel:</b> <code>{settings.CHANNEL_ID}</code>"

    await message.answer(text=help_text, parse_mode="HTML")


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    """Handle /cancel command to reset state."""
    await state.clear()
    is_admin = settings.is_admin(message.from_user.id) if message.from_user else False
    await message.answer(
        text="🛑 <i>Operation cancelled. Returned to main menu.</i>",
        reply_markup=build_main_menu_kb(is_admin=is_admin),
        parse_mode="HTML",
    )


@router.callback_query(NavCB.filter(F.to.in_(["menu", "cancel"])))
async def handle_navigation(
    callback: types.CallbackQuery, callback_data: NavCB, state: FSMContext
) -> None:
    """Handle top-level navigation callbacks (menu, cancel, stats, lb)."""
    user_id = callback.from_user.id
    is_admin = settings.is_admin(user_id)

    if callback_data.to == "menu":
        await state.clear()
        try:
            await callback.message.edit_text(
                text="🏠 <b>Main Menu Dashboard</b>\n<i>Choose a practice module or view your progress:</i>",
                reply_markup=build_main_menu_kb(is_admin=is_admin),
                parse_mode="HTML",
            )
        except Exception:
            await callback.message.answer(
                text="🏠 <b>Main Menu Dashboard</b>",
                reply_markup=build_main_menu_kb(is_admin=is_admin),
                parse_mode="HTML",
            )
        await callback.answer()

    elif callback_data.to == "cancel":
        await state.clear()
        await callback.message.edit_text(
            text="🛑 <i>Quiz cancelled. Returned to main menu.</i>",
            reply_markup=build_main_menu_kb(is_admin=is_admin),
            parse_mode="HTML",
        )
        await callback.answer("Cancelled")
