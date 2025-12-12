from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main_kb(lang: str = "ru"):
    b = InlineKeyboardBuilder()
    b.button(text="Метрики" if lang == "ru" else "Metrics", callback_data="admin:metrics")
    b.button(text="Пользователи" if lang == "ru" else "Users", callback_data="admin:users")
    b.button(text="Активные чаты" if lang == "ru" else "Active chats", callback_data="admin:chats")
    b.button(text="Жалобы" if lang == "ru" else "Reports", callback_data="admin:reports")
    b.button(text="Игры/режимы" if lang == "ru" else "Games", callback_data="admin:games")
    b.button(text="Рассылка" if lang == "ru" else "Broadcast", callback_data="admin:broadcast")
    b.button(text="Реэнгейджмент" if lang == "ru" else "Re-engage", callback_data="admin:reengage")
    b.button(text="В меню" if lang == "ru" else "Menu", callback_data="menu")
    b.adjust(2, 2, 2, 1, 1)
    return b.as_markup()


def admin_back_kb(lang: str = "ru"):
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад" if lang == "ru" else "⬅️ Back", callback_data="admin:back")
    return b.as_markup()


def admin_users_actions_kb(user_id: int, is_banned: bool, has_chat: bool, lang: str = "ru"):
    b = InlineKeyboardBuilder()
    b.button(
        text="Забанить" if lang == "ru" else "Ban",
        callback_data=f"admin_user_ban:{user_id}",
    )
    b.button(
        text="Разбанить" if lang == "ru" else "Unban",
        callback_data=f"admin_user_unban:{user_id}",
    )
    b.button(
        text="Удалить профиль" if lang == "ru" else "Delete profile",
        callback_data=f"admin_user_delete:{user_id}",
    )
    if has_chat:
        b.button(
            text="Завершить чат" if lang == "ru" else "End chat",
            callback_data=f"admin_user_endchat:{user_id}",
        )
    b.button(text="⬅️ Назад" if lang == "ru" else "⬅️ Back", callback_data="admin:users")
    b.adjust(2, 2, 1)
    return b.as_markup()


def admin_chats_kb(chats: list[tuple[int, str]], lang: str = "ru"):
    b = InlineKeyboardBuilder()
    for chat_id, label in chats:
        b.button(text=f"История {chat_id}" if lang == "ru" else f"History {chat_id}", callback_data=f"admin_chat_history:{chat_id}")
        b.button(text=f"Закрыть {chat_id}" if lang == "ru" else f"Close {chat_id}", callback_data=f"admin_chat_close:{chat_id}")
    b.button(text="⬅️ Назад" if lang == "ru" else "⬅️ Back", callback_data="admin:back")
    b.adjust(2)
    return b.as_markup()


def admin_games_kb(lang: str = "ru"):
    b = InlineKeyboardBuilder()
    b.button(text="Добавить игру" if lang == "ru" else "Add game", callback_data="admin_games:add")
    b.button(text="Удалить игру" if lang == "ru" else "Remove game", callback_data="admin_games:remove")
    b.button(text="Синхронизировать" if lang == "ru" else "Reload", callback_data="admin_games:reload")
    b.button(text="⬅️ Назад" if lang == "ru" else "⬅️ Back", callback_data="admin:back")
    b.adjust(2, 1, 1)
    return b.as_markup()


def admin_reengage_kb(lang: str = "ru"):
    b = InlineKeyboardBuilder()
    b.button(text="Запустить проверку" if lang == "ru" else "Run check", callback_data="admin_reengage:run")
    b.button(text="Статистика" if lang == "ru" else "Stats", callback_data="admin_reengage:stats")
    b.button(text="⬅️ Назад" if lang == "ru" else "⬅️ Back", callback_data="admin:back")
    b.adjust(2, 1)
    return b.as_markup()


def admin_reports_kb(report_ids: list[int], lang: str = "ru"):
    b = InlineKeyboardBuilder()
    for rid in report_ids:
        b.button(text=f"Жалоба {rid}" if lang == "ru" else f"Report {rid}", callback_data=f"admin_report:{rid}")
    b.button(text="⬅️ Назад" if lang == "ru" else "⬅️ Back", callback_data="admin:back")
    b.adjust(1)
    return b.as_markup()

