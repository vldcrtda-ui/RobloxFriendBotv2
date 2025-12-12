from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder


def match_actions_kb(offer_id: int, lang: str):
    b = InlineKeyboardBuilder()
    b.button(
        text="Предложить чат" if lang == "ru" else "Offer chat",
        callback_data=f"offer_chat:{offer_id}",
    )
    b.button(
        text="Пропустить" if lang == "ru" else "Skip",
        callback_data=f"offer_skip:{offer_id}",
    )
    b.button(
        text="Заблокировать" if lang == "ru" else "Block",
        callback_data=f"offer_block:{offer_id}",
    )
    b.adjust(1)
    return b.as_markup()


def direct_request_kb(offer_id: int, lang: str):
    b = InlineKeyboardBuilder()
    b.button(
        text="Принять чат" if lang == "ru" else "Accept chat",
        callback_data=f"offer_chat:{offer_id}",
    )
    b.button(
        text="Отклонить" if lang == "ru" else "Decline",
        callback_data=f"offer_skip:{offer_id}",
    )
    b.button(
        text="Заблокировать" if lang == "ru" else "Block",
        callback_data=f"offer_block:{offer_id}",
    )
    b.adjust(1)
    return b.as_markup()


def search_cancel_kb(lang: str):
    b = InlineKeyboardBuilder()
    b.button(text="Отменить поиск" if lang == "ru" else "Cancel search", callback_data="search_cancel")
    return b.as_markup()

