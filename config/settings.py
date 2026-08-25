"""Application settings loaded from environment variables."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    monday_api_token: str = Field(..., alias="MONDAY_API_TOKEN")
    monday_work_orders_board_id: str = Field(..., alias="MONDAY_WORK_ORDERS_BOARD_ID")
    monday_deals_board_id: str = Field(..., alias="MONDAY_DEALS_BOARD_ID")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")
    monday_api_url: str = Field(
        default="https://api.monday.com/v2",
        alias="MONDAY_API_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Pipeline probability weights (configurable in one place)
    prob_weight_high: float = 0.70
    prob_weight_medium: float = 0.40
    prob_weight_low: float = 0.15

    # Cache TTLs (seconds)
    schema_cache_ttl: int = 300
    items_cache_ttl: int = 120

    # Agent
    max_tool_rounds: int = Field(default=3, alias="MAX_TOOL_ROUNDS")
    dashboard_cache_ttl: int = Field(default=180, alias="DASHBOARD_CACHE_TTL")
    max_history_messages: int = Field(default=6, alias="MAX_HISTORY_MESSAGES")
    max_output_tokens: int = Field(default=800, alias="MAX_OUTPUT_TOKENS")
    max_context_tokens: int = Field(default=6000, alias="MAX_CONTEXT_TOKENS")
    debug_token_usage: bool = Field(default=False, alias="DEBUG_TOKEN_USAGE")
    debug_mode: bool = Field(default=False, alias="DEBUG_MODE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
