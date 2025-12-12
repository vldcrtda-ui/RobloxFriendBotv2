from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder


def broadcast_confirm_kb(lang: str):
    b = InlineKeyboardBuilder()
    b.button(text="Отправить" if lang == "ru" else "Send", callback_data="broadcast_yes")
    b.button(text="Отмена" if lang == "ru" else "Cancel", callback_data="broadcast_no")
    b.adjust(2)
    return b.as_markup()

