from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    admin_ids: str = ""
    main_admin_id: int | None = None
    reengage_after_hours: int = 72
    reengage_check_interval_min: int = 360

    @property
    def admin_id_set(self) -> set[int]:
        ids: set[int] = set()
        if self.admin_ids:
            for part in self.admin_ids.split(","):
                part = part.strip()
                if part:
                    try:
                        ids.add(int(part))
                    except ValueError:
                        continue
        if self.main_admin_id:
            ids.add(self.main_admin_id)
        return ids


settings = Settings()

