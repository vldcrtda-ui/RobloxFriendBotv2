from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder


def active_chat_kb(lang: str):
    b = InlineKeyboardBuilder()
    b.button(text="Завершить чат" if lang == "ru" else "End chat", callback_data="chat_end")
    b.button(text="Пожаловаться" if lang == "ru" else "Report", callback_data="chat_report")
    b.button(text="Заблокировать" if lang == "ru" else "Block", callback_data="chat_block")
    b.adjust(1)
    return b.as_markup()


def report_reasons_kb(lang: str):
    reasons = [
        ("spam", "Спам" if lang == "ru" else "Spam"),
        ("toxic", "Оскорбления" if lang == "ru" else "Abuse"),
        ("scam", "Скам/обман" if lang == "ru" else "Scam"),
        ("other", "Другое" if lang == "ru" else "Other"),
    ]
    b = InlineKeyboardBuilder()
    for code, label in reasons:
        b.button(text=label, callback_data=f"report:{code}")
    b.button(text="Отмена" if lang == "ru" else "Cancel", callback_data="report_cancel")
    b.adjust(2, 2, 1)
    return b.as_markup()

