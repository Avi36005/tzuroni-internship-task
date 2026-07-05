"""
Launch the interactive Telegram bot for the Weather Prediction AI Trading Agent.

Usage:
    PYTHONPATH=. python scripts/run_bot.py

Then open Telegram, message your bot (e.g. @TzuroniWeatherAgentbot), and send /help.
Requires TELEGRAM_TOKEN (and optionally TELEGRAM_CHAT_ID to restrict who can command it).
"""
import asyncio
import logging

from app.database.db import init_db
from app.notifications.telegram_bot import TelegramBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main():
    await init_db()
    bot = TelegramBot()
    print("🤖 Telegram bot is running. Press Ctrl+C to stop.")
    try:
        await bot.run_forever()
    except KeyboardInterrupt:
        bot.stop()
        print("\nBot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
