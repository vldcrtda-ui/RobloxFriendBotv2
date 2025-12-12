from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder


def profile_kb(lang: str):
    b = InlineKeyboardBuilder()
    b.button(text="Ник" if lang == "ru" else "Nickname", callback_data="profile_edit:nick")
    b.button(text="Возраст" if lang == "ru" else "Age", callback_data="profile_edit:age")
    b.button(text="Язык" if lang == "ru" else "Language", callback_data="profile_edit:lang")
    b.button(text="Режимы" if lang == "ru" else "Modes", callback_data="profile_edit:modes")
    b.button(text="Описание" if lang == "ru" else "Bio", callback_data="profile_edit:bio")
    b.button(text="Аватар" if lang == "ru" else "Avatar", callback_data="profile_edit:avatar")
    b.button(text="Удалить профиль" if lang == "ru" else "Delete profile", callback_data="profile_delete")
    b.button(text="В меню" if lang == "ru" else "Menu", callback_data="menu")
    b.adjust(2, 2, 2, 1, 1)
    return b.as_markup()

