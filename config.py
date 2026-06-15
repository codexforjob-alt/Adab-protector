from dataclasses import dataclass
from pathlib import Path
from os import getenv

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_path: str
    user_cooldown_seconds: int
    chat_cooldown_seconds: int
    flood_messages_limit: int
    flood_time_window_seconds: int
    caps_min_length: int
    caps_ratio: float
    webhook_base_url: str
    webhook_path: str
    webhook_secret_token: str
    web_host: str
    web_port: int


def _get_int(name: str, default: int) -> int:
    raw = getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _get_float(name: str, default: float) -> float:
    raw = getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _get_bool(name: str, default: bool) -> bool:
    raw = getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    env_path = Path(__file__).with_name(".env")
    if env_path.exists():
        load_dotenv(env_path)
    else:
        project_env_path = Path(__file__).resolve().parents[1] / ".env"
        if project_env_path.exists():
            load_dotenv(project_env_path)

    bot_token = getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set. Create .env from .env.example first.")

    return Config(
        bot_token=bot_token,
        database_path=getenv("DATABASE_PATH", "adab_bot.sqlite3"),
        user_cooldown_seconds=_get_int("USER_COOLDOWN_SECONDS", 120),
        chat_cooldown_seconds=_get_int("CHAT_COOLDOWN_SECONDS", 30),
        flood_messages_limit=_get_int("FLOOD_MESSAGES_LIMIT", 5),
        flood_time_window_seconds=_get_int("FLOOD_TIME_WINDOW_SECONDS", 20),
        caps_min_length=_get_int("CAPS_MIN_LENGTH", 15),
        caps_ratio=_get_float("CAPS_RATIO", 0.7),
        webhook_base_url=(
            getenv("WEBHOOK_BASE_URL", "").strip()
            or getenv("RENDER_EXTERNAL_URL", "").strip()
        ).rstrip("/"),
        webhook_path=getenv("WEBHOOK_PATH", "/telegram-webhook").strip() or "/telegram-webhook",
        webhook_secret_token=getenv("WEBHOOK_SECRET_TOKEN", "").strip(),
        web_host=getenv("WEB_HOST", "0.0.0.0").strip() or "0.0.0.0",
        web_port=_get_int("PORT", 8080),
    )
