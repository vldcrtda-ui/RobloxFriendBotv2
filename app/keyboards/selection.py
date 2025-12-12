from __future__ import annotations

import re
from difflib import SequenceMatcher

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.games import games_service
from app.utils.i18n import t

_SPACE_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _SPACE_RE.sub(" ", (text or "").casefold().replace("_", " ").replace("-", " ")).strip()


def _game_matches_query(game: dict, query_norm: str, tokens: list[str]) -> bool:
    if not tokens:
        return True

    code = str(game.get("code") or "")
    name_ru = str(game.get("name_ru") or "")
    name_en = str(game.get("name_en") or "")
    haystack = _norm(f"{code} {name_ru} {name_en}")

    if all(token in haystack for token in tokens):
        return True

    best_ratio = max(
        SequenceMatcher(None, query_norm, _norm(code)).ratio(),
        SequenceMatcher(None, query_norm, _norm(name_ru)).ratio(),
        SequenceMatcher(None, query_norm, _norm(name_en)).ratio(),
    )
    return best_ratio >= 0.72


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


def modes_kb(prefix: str, lang: str, selected: list[str], query: str | None = None):
    b = InlineKeyboardBuilder()
    query_norm = _norm(query or "")
    tokens = query_norm.split()
    selected_set = set(selected)

    games = games_service.list()
    matched = [g for g in games if _game_matches_query(g, query_norm, tokens)]
    to_show = [g for g in games if g.get("code") in selected_set] + [g for g in matched if g.get("code") not in selected_set]

    if query_norm and not to_show:
        b.button(
            text="Ничего не найдено" if lang == "ru" else "No matches",
            callback_data=f"{prefix}:__noop",
        )
    for game in to_show:
        code = game.get("code")
        label = game.get("name_en") if lang == "en" else game.get("name_ru")
        text = f"✅ {label}" if code in selected else str(label)
        b.button(text=text, callback_data=f"{prefix}:{code}")

    if query_norm:
        b.button(text="❌ Сброс" if lang == "ru" else "❌ Clear", callback_data=f"{prefix}:__clear")
    b.button(text="🔍 Поиск" if lang == "ru" else "🔍 Search", callback_data=f"{prefix}:__search")
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
