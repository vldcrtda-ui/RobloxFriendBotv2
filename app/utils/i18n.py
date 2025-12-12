from __future__ import annotations

TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "welcome_new": "Привет! Давай настроим профиль Roblox.",
        "welcome_back": "С возвращением! Что делаем дальше?",
        "ask_nick": "Введи свой ник в Roblox:",
        "nick_taken": "Этот ник уже занят в базе. Введи другой.",
        "ask_age": "Сколько тебе лет? (8–99)",
        "ask_lang": "Выбери язык интерфейса и поиска:",
        "ask_modes": "Выбери до 5 режимов/игр, которые тебе интересны:",
        "ask_bio": "Напиши короткое описание о себе (до 200 символов):",
        "ask_avatar": "Пришли аватар (фото) или нажми «Пропустить».",
        "reg_done": "Профиль создан!",
        "menu_hint": "Выбери действие:",
        "not_registered": "Сначала зарегистрируйся через /start.",
        "searching": "Идёт поиск…",
        "search_canceled": "Поиск отменён.",
        "match_found": "Нашли напарника!",
        "offer_sent": "Запрос на чат отправлен.",
        "offer_received": "Пользователь предлагает чат. Принять?",
        "chat_started": "Чат начат. Пиши сообщения сюда.",
        "chat_ended": "Чат завершён.",
        "blocked": "Пользователь заблокирован.",
        "help": "Команды: /browse /search /chat /profile /blocklist /exit_chat /cancel /help",
        "skip": "Пропустить",
        "cancel": "Отменить",
    },
    "en": {
        "welcome_new": "Hi! Let's set up your Roblox profile.",
        "welcome_back": "Welcome back! What next?",
        "ask_nick": "Enter your Roblox nickname:",
        "nick_taken": "This nickname is already used. Try another.",
        "ask_age": "How old are you? (8–99)",
        "ask_lang": "Choose your language:",
        "ask_modes": "Pick up to 5 modes/games you like:",
        "ask_bio": "Write a short bio (up to 200 chars):",
        "ask_avatar": "Send an avatar photo or tap Skip.",
        "reg_done": "Profile created!",
        "menu_hint": "Choose an action:",
        "not_registered": "Please register via /start first.",
        "searching": "Searching…",
        "search_canceled": "Search canceled.",
        "match_found": "Match found!",
        "offer_sent": "Chat request sent.",
        "offer_received": "User wants to chat. Accept?",
        "chat_started": "Chat started. Send messages here.",
        "chat_ended": "Chat ended.",
        "blocked": "User blocked.",
        "help": "Commands: /browse /search /chat /profile /blocklist /exit_chat /cancel /help",
        "skip": "Skip",
        "cancel": "Cancel",
    },
}


def t(lang: str | None, key: str, **kwargs) -> str:
    lang = lang or "ru"
    template = TEXTS.get(lang, TEXTS["ru"]).get(key, key)
    return template.format(**kwargs)

