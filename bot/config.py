"""
Configuration module - loads all settings from environment variables.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # Telegram
    TELEGRAM_TOKEN: str = ""
    TELEGRAM_OWNER_ID: int = 0

    # Ollama Cloud API
    OLLAMA_HOST: str = "https://api.ollama.com"
    OLLAMA_API_KEY: str = ""
    OLLAMA_MODEL: str = "gpt-oss:120b-cloud"

    # OpenWeatherMap
    OPENWEATHER_API_KEY: str = ""
    DEFAULT_CITY: str = "Jakarta"

    # Database
    DB_PATH: str = "/app/data/elysia.db"

    # Memory settings
    MAX_CONTEXT_MESSAGES: int = 50
    MEMORY_EXTRACTION_INTERVAL: int = 5  # Extract memories every N messages

    # Schedule check interval (seconds)
    SCHEDULE_CHECK_INTERVAL: int = 60

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            TELEGRAM_TOKEN=os.getenv("TELEGRAM_TOKEN", ""),
            TELEGRAM_OWNER_ID=int(os.getenv("TELEGRAM_OWNER_ID", "0")),
            OLLAMA_HOST=os.getenv("OLLAMA_HOST", "https://api.ollama.com"),
            OLLAMA_API_KEY=os.getenv("OLLAMA_API_KEY", ""),
            OLLAMA_MODEL=os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud"),
            OPENWEATHER_API_KEY=os.getenv("OPENWEATHER_API_KEY", ""),
            DEFAULT_CITY=os.getenv("DEFAULT_CITY", "Jakarta"),
            DB_PATH=os.getenv("DB_PATH", "/app/data/elysia.db"),
            MAX_CONTEXT_MESSAGES=int(os.getenv("MAX_CONTEXT_MESSAGES", "50")),
            MEMORY_EXTRACTION_INTERVAL=int(os.getenv("MEMORY_EXTRACTION_INTERVAL", "5")),
            SCHEDULE_CHECK_INTERVAL=int(os.getenv("SCHEDULE_CHECK_INTERVAL", "60")),
        )


config = Config.from_env()
