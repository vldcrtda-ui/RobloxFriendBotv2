from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb(lang: str):
    labels = {
        "ru": {
            "browse": "Каталог игроков",
            "search": "Поиск по фильтрам",
            "chat": "Рандом‑чат",
            "profile": "Профиль",
            "help": "Помощь",
        },
        "en": {
            "browse": "Browse players",
            "search": "Search filters",
            "chat": "Random chat",
            "profile": "Profile",
            "help": "Help",
        },
    }
    l = labels.get(lang, labels["ru"])
    b = InlineKeyboardBuilder()
    b.button(text=l["browse"], callback_data="go:browse")
    b.button(text=l["search"], callback_data="go:search")
    b.button(text=l["chat"], callback_data="go:chat")
    b.button(text=l["profile"], callback_data="go:profile")
    b.button(text=l["help"], callback_data="go:help")
    b.adjust(2, 2, 1)
    return b.as_markup()

