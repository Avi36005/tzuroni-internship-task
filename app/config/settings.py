import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # API credentials
    openrouter_api_key: str = Field(default="mock_key", validation_alias="OPENROUTER_API_KEY")
    llm_model: str = Field(default="google/gemini-2.5-flash", validation_alias="LLM_MODEL")
    apify_token: str = Field(default="", validation_alias="APIFY_TOKEN")
    
    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///weather_trading.db", validation_alias="DATABASE_URL")
    
    # Portfolio and sizing
    starting_balance: float = Field(default=10000.0, validation_alias="STARTING_BALANCE")
    kelly_fraction: float = Field(default=0.25, validation_alias="KELLY_FRACTION")
    max_exposure_per_trade: float = Field(default=0.10, validation_alias="MAX_EXPOSURE_PER_TRADE")
    daily_loss_limit: float = Field(default=0.05, validation_alias="DAILY_LOSS_LIMIT")
    
    # Telegram alerts
    telegram_token: str = Field(default="", validation_alias="TELEGRAM_TOKEN")
    telegram_chat_id: str = Field(default="", validation_alias="TELEGRAM_CHAT_ID")
    
    # App Settings
    debug: bool = Field(default=False, validation_alias="DEBUG")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
