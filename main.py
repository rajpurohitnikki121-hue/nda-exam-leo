import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import settings
from database.connection import engine, init_db
from handlers import setup_routers
from middlewares import ForceSubMiddleware, TrackUserMiddleware
from services.nda_bank import bank as nda_bank

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s : %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("telegram_quiz_bot")


async def set_bot_commands(bot: Bot) -> None:
    """Register standard commands in the Telegram client menu."""
    commands = [
        BotCommand(command="start", description="🚀 Launch Bot & Main Dashboard"),
        BotCommand(command="menu", description="🏠 Main Menu"),
        BotCommand(command="nda", description="🎖️ NDA Exam Practice (Maths / GAT)"),
        BotCommand(command="stats", description="📊 My Performance & Accuracy"),
        BotCommand(command="leaderboard", description="🏆 Channel Leaderboard"),
        BotCommand(command="help", description="📖 User Manual & Command List"),
        BotCommand(command="cancel", description="🛑 Cancel Active Flow"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot commands successfully registered with Telegram API.")
    except Exception as e:
        logger.warning(f"Could not register bot commands: {e}")


async def on_startup(bot: Bot) -> None:
    """Execute startup lifecycle tasks."""
    logger.info("Starting up Telegram Quiz Bot...")

    # Initialize and auto-seed database
    await init_db()

    # Load NDA question bank (data/nda/*.json)
    nda_bank.load()

    # Set bot commands in Telegram UI
    await set_bot_commands(bot)

    # Fetch bot metadata
    try:
        me = await bot.get_me()
        logger.info(f"Bot authenticated successfully: @{me.username} (ID: {me.id})")
        logger.info(f"Connected Channel ID: {settings.CHANNEL_ID}")
        logger.info(f"Configured Admin IDs: {settings.admin_id_list}")
    except Exception as e:
        logger.warning(f"Could not connect to Telegram API during startup: {e}")


async def on_shutdown(bot: Bot) -> None:
    """Execute graceful shutdown lifecycle tasks."""
    logger.info("Shutting down bot...")
    await bot.session.close()
    await engine.dispose()
    logger.info("Bot shutdown complete.")


async def main() -> None:
    """Central bot runner function."""
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Track + log every user (saves them in DB, prints NEW USER / COMMAND lines)
    dp.message.outer_middleware(TrackUserMiddleware())
    dp.callback_query.outer_middleware(TrackUserMiddleware())
    # Force-subscribe gate (runs after tracking, so blocked users are still saved)
    dp.message.outer_middleware(ForceSubMiddleware())
    dp.callback_query.outer_middleware(ForceSubMiddleware())

    # Register all modular routers
    root_router = setup_routers()
    dp.include_router(root_router)

    # Register lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting long polling...")
    try:
        # Delete webhook before starting polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Received termination signal.")
    except Exception as e:
        logger.error(f"Unexpected error in bot main loop: {e}", exc_info=True)
    finally:
        await on_shutdown(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
