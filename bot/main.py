"""
Main entry point for the Elysia Telegram Chatbot.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.config import config
from bot.memory import MemoryManager
from bot.elysia import ElysiaBrain
from bot.telegram_handler import TelegramHandler
from bot.services.weather import WeatherService
from bot.services.traffic import TrafficService
from bot.services.schedule import ScheduleService
from bot.services.search import SearchService

# ── Logging Setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("elysia")


def validate_config():
    """Validate required configuration."""
    errors = []
    if not config.TELEGRAM_TOKEN:
        errors.append("TELEGRAM_TOKEN is not set")
    if not config.TELEGRAM_OWNER_ID:
        errors.append("TELEGRAM_OWNER_ID is not set")
    if not config.OLLAMA_API_KEY:
        errors.append("OLLAMA_API_KEY is not set")

    if errors:
        for err in errors:
            logger.error(f"❌ Config error: {err}")
        logger.error("Please check your .env file or environment variables.")
        sys.exit(1)

    if not config.OPENWEATHER_API_KEY:
        logger.warning("⚠️ OPENWEATHER_API_KEY not set — weather features will be limited")


def main():
    """Initialize and start the bot."""
    logger.info("=" * 60)
    logger.info("🌸 Elysia Telegram Chatbot - Starting Up...")
    logger.info("=" * 60)

    # Validate config
    validate_config()

    logger.info(f"📡 Ollama Host: {config.OLLAMA_HOST}")
    logger.info(f"🤖 Model: {config.OLLAMA_MODEL}")
    logger.info(f"👤 Owner ID: {config.TELEGRAM_OWNER_ID}")
    logger.info(f"💾 Database: {config.DB_PATH}")

    # Initialize services
    memory = MemoryManager(config.DB_PATH)
    weather = WeatherService(config.OPENWEATHER_API_KEY)
    traffic = TrafficService()
    schedule_svc = ScheduleService()
    search = SearchService()

    logger.info("✅ Services initialized")

    # Initialize Elysia brain
    brain = ElysiaBrain(memory, weather, traffic, schedule_svc, search)
    logger.info("✅ Elysia brain initialized")

    # Initialize Telegram handler and start polling
    handler = TelegramHandler(brain)
    app = handler.build_app()

    logger.info("🌸 Elysia is now online and ready to chat! 💕")
    logger.info("=" * 60)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
