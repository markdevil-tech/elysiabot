"""
Telegram bot handler.
Routes messages through Elysia's brain and handles commands.
"""
import asyncio
import logging
from datetime import datetime
import pytz

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ChatAction

from bot.config import config
from bot.elysia import ElysiaBrain

logger = logging.getLogger(__name__)


class TelegramHandler:
    """Handles all Telegram interactions."""

    def __init__(self, brain: ElysiaBrain):
        self.brain = brain
        self.app: Application = None

    async def _is_owner(self, update: Update) -> bool:
        """Check if message is from the owner."""
        user_id = update.effective_user.id
        if user_id != config.TELEGRAM_OWNER_ID:
            await update.message.reply_text(
                "Maaf, aku hanya bisa ngobrol dengan owner-ku~ 💕"
            )
            return False
        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not await self._is_owner(update):
            return

        await update.message.chat.send_action(ChatAction.TYPING)
        greeting = await self.brain.get_greeting()
        await update.message.reply_text(greeting)

    async def cmd_cuaca(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cuaca command."""
        if not await self._is_owner(update):
            return

        await update.message.chat.send_action(ChatAction.TYPING)
        city = " ".join(context.args) if context.args else config.DEFAULT_CITY
        response = await self.brain.think(f"Bagaimana cuaca di {city} sekarang?")
        await update.message.reply_text(response)

    async def cmd_jadwal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /jadwal command."""
        if not await self._is_owner(update):
            return

        await update.message.chat.send_action(ChatAction.TYPING)
        response = await self.brain.think("Tolong lihatkan semua jadwal saya.")
        await update.message.reply_text(response)

    async def cmd_traffic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /traffic command."""
        if not await self._is_owner(update):
            return

        await update.message.chat.send_action(ChatAction.TYPING)
        response = await self.brain.think("Bagaimana kondisi lalu lintas sekarang?")
        await update.message.reply_text(response)

    async def cmd_memory(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /memory command - show what Elysia remembers."""
        if not await self._is_owner(update):
            return

        await update.message.chat.send_action(ChatAction.TYPING)
        memories = self.brain.memory.get_all_memories()
        if memories:
            mem_text = "\n".join([f"• [{m['category']}] {m['content']}" for m in memories])
            response = await self.brain.think(f"Ini adalah hal-hal yang kamu ingat tentang aku, tolong rangkum dengan gayamu: {mem_text}")
        else:
            response = await self.brain.think("Aku belum pernah cerita apa-apa tentang diriku ya? Apa yang kamu ingat tentang aku?")
        await update.message.reply_text(response)

    async def cmd_cari(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cari command - search the internet."""
        if not await self._is_owner(update):
            return

        query = " ".join(context.args) if context.args else ""
        if not query:
            await update.message.reply_text("Mau cari apa dear~? Tulis /cari [kata kunci] ya 💕")
            return

        await update.message.chat.send_action(ChatAction.TYPING)
        response = await self.brain.think(f"Tolong carikan informasi tentang: {query}")
        await update.message.reply_text(response)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages."""
        if not await self._is_owner(update):
            return

        user_message = update.message.text
        if not user_message:
            return

        await update.message.chat.send_action(ChatAction.TYPING)

        try:
            response = await self.brain.think(user_message)

            # Split long messages (Telegram limit is 4096 chars)
            if len(response) > 4000:
                parts = self._split_message(response, 4000)
                for part in parts:
                    await update.message.reply_text(part)
                    await asyncio.sleep(0.5)
            else:
                await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Message handling error: {e}", exc_info=True)
            await update.message.reply_text(
                "Aduh, aku lagi sedikit error nih dear~ Coba lagi ya? 🥺"
            )

    def _split_message(self, text: str, max_len: int) -> list:
        """Split a long message at natural break points."""
        parts = []
        while len(text) > max_len:
            # Find last newline before limit
            split_idx = text.rfind('\n', 0, max_len)
            if split_idx == -1:
                split_idx = text.rfind(' ', 0, max_len)
            if split_idx == -1:
                split_idx = max_len

            parts.append(text[:split_idx])
            text = text[split_idx:].lstrip()
        if text:
            parts.append(text)
        return parts

    async def schedule_reminder_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Periodic job to check for schedule reminders."""
        try:
            unreminded = self.brain.memory.get_unreminded_schedules()
            for schedule in unreminded:
                title = schedule.get("title", "")
                time = schedule.get("event_time", "")
                desc = schedule.get("description", "")

                reminder_text = await self.brain.think(
                    f"[SISTEM: Ingatkan user bahwa sekarang waktunya untuk '{title}' "
                    f"yang dijadwalkan jam {time}. Deskripsi: {desc}. Ingatkan dengan gayamu yang khas!]"
                )

                await context.bot.send_message(
                    chat_id=config.TELEGRAM_OWNER_ID,
                    text=f"⏰ PENGINGAT!\n\n{reminder_text}"
                )
                self.brain.memory.mark_reminded(schedule["id"])

        except Exception as e:
            logger.error(f"Reminder job error: {e}")

    async def morning_briefing_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Send a morning briefing at 6:30 AM."""
        now = datetime.now()
        if now.weekday() >= 5:  # Skip weekends
            return

        try:
            briefing = await self.brain.think(
                "[SISTEM: Berikan morning briefing untuk user. "
                "Sertakan: sapaan pagi, jadwal hari ini, kondisi cuaca, "
                "dan kondisi lalu lintas untuk berangkat kerja. "
                "Berikan semua info ini dalam satu pesan yang natural dan ceria.]"
            )
            await context.bot.send_message(
                chat_id=config.TELEGRAM_OWNER_ID,
                text=f"🌅 Selamat Pagi!\n\n{briefing}"
            )
        except Exception as e:
            logger.error(f"Morning briefing error: {e}")

    async def evening_traffic_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Send evening traffic update at 4:30 PM on weekdays."""
        now = datetime.now()
        if now.weekday() >= 5:
            return

        try:
            update = await self.brain.think(
                "[SISTEM: Beritahu user tentang kondisi lalu lintas sore ini "
                "untuk perjalanan pulang kerja. Berikan saran waktu pulang yang optimal.]"
            )
            await context.bot.send_message(
                chat_id=config.TELEGRAM_OWNER_ID,
                text=f"🚗 Update Lalu Lintas\n\n{update}"
            )
        except Exception as e:
            logger.error(f"Evening traffic error: {e}")

    async def post_init(self, application: Application):
        """Set up commands and scheduled jobs after initialization."""
        commands = [
            BotCommand("start", "Mulai ngobrol dengan Elysia~"),
            BotCommand("cuaca", "Cek cuaca (contoh: /cuaca Jakarta)"),
            BotCommand("jadwal", "Lihat semua jadwal"),
            BotCommand("traffic", "Cek kondisi lalu lintas"),
            BotCommand("memory", "Lihat apa yang Elysia ingat"),
            BotCommand("cari", "Cari info di internet"),
        ]
        await application.bot.set_my_commands(commands)

        # Set up scheduled jobs
        job_queue = application.job_queue
        if job_queue:
            # Check reminders every minute
            job_queue.run_repeating(
                self.schedule_reminder_job,
                interval=config.SCHEDULE_CHECK_INTERVAL,
                first=10,
            )
            # Morning briefing at 6:30 AM WIB (23:30 UTC previous day)
            from datetime import time as dt_time
            job_queue.run_daily(
                self.morning_briefing_job,
                time=dt_time(hour=6, minute=30),
            )
            # Evening traffic at 4:30 PM WIB (09:30 UTC)
            job_queue.run_daily(
                self.evening_traffic_job,
                time=dt_time(hour=16, minute=30),
            )
            logger.info("✅ Scheduled jobs registered successfully")

    def build_app(self) -> Application:
        """Build and configure the Telegram application."""
        self.app = (
            Application.builder()
            .token(config.TELEGRAM_TOKEN)
            .post_init(self.post_init)
            .build()
        )

        # Set timezone to Jakarta for scheduled jobs
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        self.app.job_queue.scheduler.timezone = jakarta_tz

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("cuaca", self.cmd_cuaca))
        self.app.add_handler(CommandHandler("jadwal", self.cmd_jadwal))
        self.app.add_handler(CommandHandler("traffic", self.cmd_traffic))
        self.app.add_handler(CommandHandler("memory", self.cmd_memory))
        self.app.add_handler(CommandHandler("cari", self.cmd_cari))
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))

        logger.info("✅ Telegram bot handlers registered")
        return self.app
