from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.games import games_service
from app.utils.i18n import t


def language_kb(prefix: str, lang: str, selected: str | None = None, include_any: bool = False):
    b = InlineKeyboardBuilder()
    options = []
    if include_any:
        options.append(("any", "Любой" if lang == "ru" else "Any"))
    options += [
        ("ru", "Русский"),
        ("en", "English"),
    ]
    for code, label in options:
        text = f"✅ {label}" if selected == code else label
        b.button(text=text, callback_data=f"{prefix}:{code}")
    b.adjust(2)
    return b.as_markup()


def modes_kb(prefix: str, lang: str, selected: list[str]):
    b = InlineKeyboardBuilder()
    for game in games_service.list():
        code = game.get("code")
        label = game.get("name_en") if lang == "en" else game.get("name_ru")
        text = f"✅ {label}" if code in selected else str(label)
        b.button(text=text, callback_data=f"{prefix}:{code}")
    done_text = "Готово" if lang == "ru" else "Done"
    b.button(text=done_text, callback_data=f"{prefix}:done")
    b.adjust(2)
    return b.as_markup()


def skip_kb(callback_data: str, lang: str):
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "skip"), callback_data=callback_data)
    return b.as_markup()


def confirm_kb(yes_cb: str, no_cb: str, lang: str, yes_text: str | None = None, no_text: str | None = None):
    b = InlineKeyboardBuilder()
    b.button(text=yes_text or ("Да" if lang == "ru" else "Yes"), callback_data=yes_cb)
    b.button(text=no_text or ("Нет" if lang == "ru" else "No"), callback_data=no_cb)
    b.adjust(2)
    return b.as_markup()

