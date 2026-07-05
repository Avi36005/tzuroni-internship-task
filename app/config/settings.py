import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # LLM API credentials & provider configuration
    openrouter_api_key: str = Field(default="mock_key", validation_alias="OPENROUTER_API_KEY")
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    # Optional additional Groq keys for round-robin + rate-limit failover (doubles effective TPM).
    groq_api_key_fallback: str = Field(default="", validation_alias="GROQ_API_KEY_FALLBACK")
    llm_model: str = Field(default="google/gemini-2.5-flash", validation_alias="LLM_MODEL")
    # Optional explicit overrides; when unset the provider is auto-selected (Groq > OpenRouter).
    llm_base_url: str = Field(default="", validation_alias="LLM_BASE_URL")
    # Use the Nous Research Hermes Agent framework as the reasoning backend when available.
    use_hermes: bool = Field(default=True, validation_alias="USE_HERMES")

    apify_token: str = Field(default="", validation_alias="APIFY_TOKEN")
    
    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///weather_trading.db", validation_alias="DATABASE_URL")

    # Polymarket access. Polymarket geoblocks several regions; set a proxy (e.g. a VPN's
    # HTTP/SOCKS proxy URL) to reach the real API. When the real API is unreachable and
    # allow_simulated_markets is False, the system trades no markets rather than fabricating them.
    polymarket_proxy: str = Field(default="", validation_alias="POLYMARKET_PROXY")
    allow_simulated_markets: bool = Field(default=True, validation_alias="ALLOW_SIMULATED_MARKETS")
    
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
