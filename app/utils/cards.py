from __future__ import annotations

from app.services.games import games_service


def format_profile(user, lang: str, show_id: bool = False) -> str:
    modes = games_service.labels(user.modes or [], lang)
    modes_text = ", ".join(modes) if modes else "-"
    text = (
        f"<b>{user.roblox_nick}</b>\n"
        f"Возраст: {user.age}\n"
        f"Язык: {user.language}\n"
        f"Режимы: <code>{modes_text}</code>\n"
    )
    if user.bio:
        text += f"{user.bio}\n"
    if show_id:
        text += f"\nID: <code>{user.id}</code>"
    return text.strip()

