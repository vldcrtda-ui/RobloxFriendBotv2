from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder


def browse_nav_kb(target_id: int, index: int, total: int, lang: str):
    b = InlineKeyboardBuilder()
    prev_text = "⬅️" if index > 0 else "—"
    next_text = "➡️" if index < total - 1 else "—"
    b.button(text=prev_text, callback_data="browse_prev")
    b.button(text=f"{index+1}/{total}", callback_data="noop")
    b.button(text=next_text, callback_data="browse_next")
    b.button(
        text="Предложить чат" if lang == "ru" else "Offer chat",
        callback_data=f"browse_offer:{target_id}",
    )
    b.button(
        text="Фильтры" if lang == "ru" else "Filters",
        callback_data="browse_filters",
    )
    b.button(text="В меню" if lang == "ru" else "Menu", callback_data="menu")
    b.adjust(3, 1, 2)
    return b.as_markup()


def browse_filters_kb(lang: str):
    b = InlineKeyboardBuilder()
    b.button(text="Язык" if lang == "ru" else "Language", callback_data="browse_set_lang")
    b.button(text="Возраст" if lang == "ru" else "Age", callback_data="browse_set_age")
    b.button(text="Режимы" if lang == "ru" else "Modes", callback_data="browse_set_modes")
    b.button(text="Сбросить" if lang == "ru" else "Reset", callback_data="browse_reset")
    b.button(text="Назад" if lang == "ru" else "Back", callback_data="browse_back")
    b.adjust(2, 2, 1)
    return b.as_markup()

