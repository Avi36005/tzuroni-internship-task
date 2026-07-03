import logging
import httpx
from typing import Optional
from app.config.settings import settings

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Notifier for sending trade alerts and portfolio updates to a Telegram channel/chat"""
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None, client: Optional[httpx.AsyncClient] = None):
        self.token = token or settings.telegram_token
        self.chat_id = chat_id or settings.telegram_chat_id
        self.client = client or httpx.AsyncClient(timeout=10.0)

    async def send_message(self, message: str) -> bool:
        """Send message asynchronously to Telegram"""
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not configured. Skipping alert.")
            return False
            
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            logger.info("Sending notification to Telegram...")
            response = await self.client.post(url, json=payload)
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully.")
                return True
            else:
                logger.error(f"Telegram API returned status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}", exc_info=True)
            return False
