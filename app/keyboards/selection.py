from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.games import games_service
from app.utils.i18n import t

_PAGE_SIZE = 20


def language_kb(prefix: str, lang: str, selected: str | None = None, include_any: bool = False):
    b = InlineKeyboardBuilder()
    options: list[tuple[str, str]] = []
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


def modes_kb(prefix: str, lang: str, selected: list[str], query: str | None = None, page: int = 0):
    b = InlineKeyboardBuilder()
    selected_set = set(selected)

    for code in selected:
        game = games_service.get(code) or {"code": code, "name_ru": code, "name_en": code}
        label = game.get("name_en") if lang == "en" else game.get("name_ru")
        b.button(text=f"✅ {label}", callback_data=f"{prefix}:{code}")

    if query:
        page_items, total = games_service.search(query, page, _PAGE_SIZE, exclude_codes=selected_set)
    else:
        page_items, total = games_service.page(page, _PAGE_SIZE, exclude_codes=selected_set)

    if total == 0:
        b.button(text="Ничего не найдено" if lang == "ru" else "No matches", callback_data=f"{prefix}:__noop")
    else:
        max_page = max(0, (total - 1) // _PAGE_SIZE)
        page = max(0, min(int(page or 0), max_page))

        for game in page_items:
            code = str(game.get("code") or "")
            label = game.get("name_en") if lang == "en" else game.get("name_ru")
            b.button(text=str(label), callback_data=f"{prefix}:{code}")

        if page > 0:
            b.button(text="⬅️", callback_data=f"{prefix}:__prev")
        if (page + 1) * _PAGE_SIZE < total:
            b.button(text="➡️", callback_data=f"{prefix}:__next")

    if query:
        b.button(text="❌ Сброс" if lang == "ru" else "❌ Clear", callback_data=f"{prefix}:__clear")
    b.button(text="🔍 Поиск" if lang == "ru" else "🔍 Search", callback_data=f"{prefix}:__search")
    b.button(text="Готово" if lang == "ru" else "Done", callback_data=f"{prefix}:done")
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

