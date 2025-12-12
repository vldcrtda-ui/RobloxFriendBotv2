from __future__ import annotations

import re
from difflib import SequenceMatcher

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.games import games_service
from app.utils.i18n import t

_SPACE_RE = re.compile(r"\s+")
_PAGE_SIZE = 20

_EN_TO_RU = str.maketrans(
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.",
    "йцукенгшщзхъфывапролджэячсмитьбю",
)
_RU_TO_EN = str.maketrans(
    "йцукенгшщзхъфывапролджэячсмитьбю",
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.",
)
_RU_TO_LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _norm(text: str) -> str:
    text = (text or "").casefold().replace("_", " ").replace("-", " ")
    buf = [" " if not ch.isalnum() else ch for ch in text]
    return _SPACE_RE.sub(" ", "".join(buf)).strip()


def _translit_ru_to_lat(text: str) -> str:
    text = (text or "").casefold()
    return "".join(_RU_TO_LAT.get(ch, ch) for ch in text)


def _query_variants(query: str | None) -> list[str]:
    raw = (query or "").strip()
    if not raw:
        return []

    variants = [
        raw,
        raw.translate(_RU_TO_EN),
        raw.translate(_EN_TO_RU),
        _translit_ru_to_lat(raw),
        _translit_ru_to_lat(raw.translate(_RU_TO_EN)),
    ]
    out: list[str] = []
    for v in variants:
        nv = _norm(v)
        if nv and nv not in out:
            out.append(nv)
    return out


def _game_match_score(game: dict, query_variants: list[str]) -> float:
    code = str(game.get("code") or "")
    name_ru = str(game.get("name_ru") or "")
    name_en = str(game.get("name_en") or "")

    hay = _norm(f"{code} {name_ru} {name_en}")
    hay_lat = _norm(_translit_ru_to_lat(hay))

    targets = [
        _norm(code),
        _norm(name_ru),
        _norm(name_en),
        _norm(_translit_ru_to_lat(name_ru)),
        _norm(_translit_ru_to_lat(name_en)),
    ]

    best = 0.0
    for q in query_variants:
        if not q:
            continue
        tokens = q.split()
        if tokens:
            if all(t in hay or t in hay_lat for t in tokens):
                best = max(best, 1.0)
                continue
            matched = sum(1 for t in tokens if t in hay or t in hay_lat)
            if matched:
                best = max(best, (matched / len(tokens)) * 0.7)

        # Fuzzy
        ratio = 0.0
        for target in targets:
            if not target:
                continue
            ratio = max(ratio, SequenceMatcher(None, q, target).ratio())
        best = max(best, ratio)

    return best


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


def modes_kb(prefix: str, lang: str, selected: list[str], query: str | None = None, page: int = 0):
    b = InlineKeyboardBuilder()
    selected_set = set(selected)

    for code in selected:
        game = games_service.get(code) or {"code": code, "name_ru": code, "name_en": code}
        label = game.get("name_en") if lang == "en" else game.get("name_ru")
        b.button(text=f"✅ {label}", callback_data=f"{prefix}:{code}")

    query_variants = _query_variants(query)
    games = games_service.list()

    if query_variants:
        scored: list[tuple[float, int, dict]] = []
        for g in games:
            code = str(g.get("code") or "")
            if code in selected_set:
                continue
            score = _game_match_score(g, query_variants)
            if score < 0.55:
                continue
            popularity = int(g.get("playerCount") or 0)
            scored.append((score, popularity, g))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        total = len(scored)
        max_page = max(0, (total - 1) // _PAGE_SIZE)
        page = max(0, min(int(page or 0), max_page))
        page_items = [g for _, _, g in scored[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]]

        if total == 0:
            b.button(
                text="Ничего не найдено" if lang == "ru" else "No matches",
                callback_data=f"{prefix}:__noop",
            )
    else:
        total = max(0, len(games) - len(selected_set))
        max_page = max(0, (total - 1) // _PAGE_SIZE)
        page = max(0, min(int(page or 0), max_page))
        start = page * _PAGE_SIZE
        page_items = []
        index = 0
        for g in games:
            code = str(g.get("code") or "")
            if code in selected_set:
                continue
            if index < start:
                index += 1
                continue
            page_items.append(g)
            if len(page_items) >= _PAGE_SIZE:
                break
            index += 1

    for game in page_items:
        code = str(game.get("code") or "")
        label = game.get("name_en") if lang == "en" else game.get("name_ru")
        text = f"✅ {label}" if code in selected_set else str(label)
        b.button(text=text, callback_data=f"{prefix}:{code}")

    if page > 0:
        b.button(text="⬅️", callback_data=f"{prefix}:__prev")
    if (page + 1) * _PAGE_SIZE < total:
        b.button(text="➡️", callback_data=f"{prefix}:__next")

    if query_variants:
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
