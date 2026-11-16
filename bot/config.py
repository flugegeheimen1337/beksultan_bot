from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def load_dotenv(path: str | Path = ".env") -> None:
    file_path = Path(path)
    if not file_path.is_file():
        return
    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    bot_token: str
    timezone: str
    auto_report_hour: int
    db_path: str

    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_settings() -> Settings:
    load_dotenv()
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is not set")
    timezone_name = os.environ.get("TIMEZONE", "Asia/Dubai").strip() or "Asia/Dubai"
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise SystemExit(f"Invalid TIMEZONE: {timezone_name}") from exc
    hour_raw = os.environ.get("AUTO_REPORT_HOUR", "21").strip() or "21"
    try:
        hour = int(hour_raw)
    except ValueError as exc:
        raise SystemExit("AUTO_REPORT_HOUR must be an integer 0-23") from exc
    if not 0 <= hour <= 23:
        raise SystemExit("AUTO_REPORT_HOUR must be an integer 0-23")
    db_path = os.environ.get("DB_PATH", "./data/finance.db").strip() or "./data/finance.db"
    return Settings(
        bot_token=token,
        timezone=timezone_name,
        auto_report_hour=hour,
        db_path=db_path,
    )


class RedactToken(logging.Formatter):
    def __init__(self, token: str) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")
        self._token = token

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if self._token:
            text = text.replace(self._token, "***")
        return text


def setup_logging(token: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactToken(token))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
