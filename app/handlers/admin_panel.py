from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.keyboards.admin_panel import (
    admin_back_kb,
    admin_bans_kb,
    admin_chats_kb,
    admin_games_kb,
    admin_main_kb,
    admin_reengage_kb,
    admin_reports_kb,
    admin_users_actions_kb,
)
from app.keyboards.selection import confirm_kb
from app.keyboards.menu import main_menu_kb
from app.models.chat import ChatSession
from app.models.search import SearchRequest
from app.models.user import User
from app.repositories.chat_repo import ChatRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.report_repo import ReportRepository
from app.repositories.user_repo import UserRepository
from app.services.games import games_service
from app.services.offers import offer_service
from app.services.reengage import ReengageService
from app.utils.cards import format_profile
from app.utils.i18n import t
from app.utils.states import AdminPanelStates, BroadcastStates
from app.utils.tg import safe_answer

router = Router()

CHATS_PAGE_SIZE = 10
BANS_PAGE_SIZE = 10


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_set


async def _admin_lang(session: AsyncSession, admin_id: int) -> str:
    admin = await UserRepository(session).get(admin_id)
    return admin.language if admin else "ru"


@router.message(Command("admin"))
async def admin_cmd(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    lang = await _admin_lang(session, message.from_user.id)
    await message.answer("Админ панель:", reply_markup=admin_main_kb(lang))


@router.callback_query(F.data == "admin:back")
async def admin_back(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    lang = await _admin_lang(session, call.from_user.id)
    await call.message.answer("Админ панель:", reply_markup=admin_main_kb(lang))
    await safe_answer(call)


@router.callback_query(F.data == "admin:metrics")
async def admin_metrics(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    users_total = await session.scalar(select(func.count()).select_from(User))
    searching = await session.scalar(
        select(func.count()).select_from(SearchRequest).where(SearchRequest.status == "waiting")
    )
    active_chats = await session.scalar(
        select(func.count()).select_from(ChatSession).where(ChatSession.status == "active")
    )
    last24 = datetime.now(timezone.utc) - timedelta(hours=24)
    active24 = await session.scalar(
        select(func.count()).select_from(User).where(User.last_active_at >= last24)
    )
    text = (
        f"Пользователей: {users_total}\n"
        f"Ищут: {searching}\n"
        f"Активных чатов: {active_chats}\n"
        f"Активных за 24ч: {active24}"
    )
    lang = await _admin_lang(session, call.from_user.id)
    await call.message.answer(text, reply_markup=admin_back_kb(lang))
    await safe_answer(call)


@router.callback_query(F.data == "admin:users")
async def admin_users(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminPanelStates.user_search)
    await call.message.answer("Введи ID или ник пользователя для модерации:")
    await safe_answer(call)


@router.message(AdminPanelStates.user_search)
async def admin_user_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    query = (message.text or "").strip()
    if query.startswith("@"):
        query = query[1:].strip()
    repo = UserRepository(session)
    if query.isdigit():
        target = await repo.get(int(query))
    else:
        target = await repo.get_by_nick(query)
        if not target:
            matches = await repo.search_by_nick(query, limit=10)
            if len(matches) == 1:
                target = matches[0]
            elif len(matches) > 1:
                lines = ["Найдено несколько пользователей:"]
                lines.extend([f"- {u.id}: {u.roblox_nick}" for u in matches])
                lines.append("\nОтправьте ID или более точный ник.")
                await message.answer("\n".join(lines))
                return
    if not target:
        await message.answer("Не найден. Попробуй ещё раз или /admin.")
        return

    await state.update_data(target_id=target.id)
    lang = await _admin_lang(session, message.from_user.id)
    text = format_profile(target, lang, show_id=True)
    text += f"\nСостояние: <code>{target.state}</code>"
    text += f"\nПоследняя активность: {target.last_active_at:%Y-%m-%d %H:%M} UTC"
    if target.is_banned:
        until = target.ban_until.strftime('%Y-%m-%d %H:%M') + " UTC" if target.ban_until else "∞"
        text += f"\nБан до: {until}"
        if target.ban_reason:
            text += f"\nПричина: {target.ban_reason}"

    has_chat = target.active_chat_id is not None
    await message.answer(
        text,
        reply_markup=admin_users_actions_kb(target.id, target.is_banned, has_chat, lang),
    )


@router.callback_query(F.data.startswith("admin_user_view:"))
async def admin_user_view(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    try:
        target_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await safe_answer(call)
        return
    target = await UserRepository(session).get(target_id)
    if not target:
        await safe_answer(call)
        return

    lang = await _admin_lang(session, call.from_user.id)
    text = format_profile(target, lang, show_id=True)
    text += f"\nСостояние: <code>{target.state}</code>"
    text += f"\nПоследняя активность: {target.last_active_at:%Y-%m-%d %H:%M} UTC"
    if target.is_banned:
        until = target.ban_until.strftime("%Y-%m-%d %H:%M") + " UTC" if target.ban_until else "∞"
        text += f"\nБан до: {until}"
        if target.ban_reason:
            text += f"\nПричина: {target.ban_reason}"

    has_chat = target.active_chat_id is not None
    await call.message.answer(
        text,
        reply_markup=admin_users_actions_kb(target.id, target.is_banned, has_chat, lang),
    )
    await safe_answer(call)


@router.callback_query(F.data.startswith("admin_user_ban:"))
async def admin_user_ban_cb(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    target_id = int(call.data.split(":")[1])
    await state.set_state(AdminPanelStates.user_ban_days)
    await state.update_data(target_id=target_id)
    await call.message.answer("На сколько дней забанить? 0 = навсегда.")
    await safe_answer(call)


@router.message(AdminPanelStates.user_ban_days)
async def admin_user_ban_days(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    try:
        days = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите число дней.")
        return
    if days < 0:
        await message.answer("Дни не могут быть отрицательными.")
        return
    await state.update_data(days=days)
    await state.set_state(AdminPanelStates.user_ban_reason)
    await message.answer("Причина бана? Напиши текст или '-' чтобы пропустить.")


@router.message(AdminPanelStates.user_ban_reason)
async def admin_user_ban_reason(message: Message, state: FSMContext, session: AsyncSession, bot) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    target_id = int(data["target_id"])
    days = int(data["days"])
    reason_raw = (message.text or "").strip()
    reason = None if reason_raw in {"", "-"} else reason_raw
    until = None if days == 0 else datetime.now(timezone.utc) + timedelta(days=days)

    chat_repo = ChatRepository(session)
    chat = await chat_repo.get_active_for_user(target_id)
    if chat:
        await offer_service.close_chat_for_user(session, target_id)
        await session.commit()
        for uid in (chat.user1_id, chat.user2_id):
            u = await UserRepository(session).get(uid)
            lang_u = u.language if u else "ru"
            try:
                await bot.send_message(uid, "Чат завершён администратором.", reply_markup=main_menu_kb(lang_u))
            except Exception:
                pass

    await UserRepository(session).set_ban(target_id, until, reason)
    await session.commit()
    await state.clear()

    try:
        msg = "Вы получили бан."
        if until:
            msg += f" До {until:%Y-%m-%d %H:%M} UTC."
        if reason:
            msg += f"\nПричина: {reason}"
        await bot.send_message(target_id, msg)
    except Exception:
        pass

    lang = await _admin_lang(session, message.from_user.id)
    await message.answer("Бан выдан.", reply_markup=admin_main_kb(lang))


@router.callback_query(F.data.startswith("admin_user_unban:"))
async def admin_user_unban_cb(call: CallbackQuery, session: AsyncSession, bot) -> None:
    if not _is_admin(call.from_user.id):
        return
    target_id = int(call.data.split(":")[1])
    await UserRepository(session).clear_ban(target_id)
    await session.commit()
    try:
        await bot.send_message(target_id, "Вы были разбанены администратором.")
    except Exception:
        pass
    await call.message.answer("Разбанено.")
    await safe_answer(call)


@router.callback_query(F.data.startswith("admin_user_delete:"))
async def admin_user_delete_cb(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    target_id = int(call.data.split(":")[1])
    await state.set_state(AdminPanelStates.user_delete_confirm)
    await state.update_data(target_id=target_id)
    lang = await _admin_lang(session, call.from_user.id)
    await call.message.answer(
        "Удалить профиль пользователя? Это необратимо.",
        reply_markup=confirm_kb("admin_user_delete_yes", "admin_user_delete_no", lang),
    )
    await safe_answer(call)


@router.callback_query(AdminPanelStates.user_delete_confirm, F.data.in_({"admin_user_delete_yes", "admin_user_delete_no"}))
async def admin_user_delete_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    if not _is_admin(call.from_user.id):
        return
    data = await state.get_data()
    target_id = int(data["target_id"])
    if call.data == "admin_user_delete_yes":
        chat = await ChatRepository(session).get_active_for_user(target_id)
        if chat:
            await offer_service.close_chat_for_user(session, target_id)
        await UserRepository(session).delete(target_id)
        await session.commit()
        try:
            await bot.send_message(target_id, "Ваш профиль удалён администратором.")
        except Exception:
            pass
        await call.message.answer("Профиль удалён.")
    else:
        await call.message.answer("Отменено.")
    await state.clear()
    await safe_answer(call)


@router.callback_query(F.data.startswith("admin_user_endchat:"))
async def admin_user_endchat(call: CallbackQuery, session: AsyncSession, bot) -> None:
    if not _is_admin(call.from_user.id):
        return
    target_id = int(call.data.split(":")[1])
    chat = await ChatRepository(session).get_active_for_user(target_id)
    if not chat:
        await call.message.answer("Активного чата нет.")
        await safe_answer(call)
        return
    await offer_service.close_chat_for_user(session, target_id)
    await session.commit()
    for uid in (chat.user1_id, chat.user2_id):
        u = await UserRepository(session).get(uid)
        lang_u = u.language if u else "ru"
        try:
            await bot.send_message(uid, "Чат завершён администратором.", reply_markup=main_menu_kb(lang_u))
        except Exception:
            pass
    await call.message.answer("Чат завершён.")
    await safe_answer(call)


async def _send_bans_page(call: CallbackQuery, session: AsyncSession, offset: int) -> None:
    offset = max(0, offset)
    stmt = (
        select(User)
        .where(User.is_banned.is_(True))
        .order_by(User.id.desc())
        .offset(offset)
        .limit(BANS_PAGE_SIZE + 1)
    )
    banned = list((await session.scalars(stmt)).all())
    has_next = len(banned) > BANS_PAGE_SIZE
    banned = banned[:BANS_PAGE_SIZE]
    if not banned:
        await call.message.answer("Банов нет." if offset == 0 else "Больше банов нет.")
        await safe_answer(call)
        return

    lines = ["Бан-лист:"]
    for u in banned:
        until = u.ban_until.strftime("%Y-%m-%d %H:%M") + " UTC" if u.ban_until else "∞"
        nick = u.roblox_nick or "-"
        lines.append(f"- {u.id}: {nick} до {until}")

    lang = await _admin_lang(session, call.from_user.id)
    prev_offset = offset - BANS_PAGE_SIZE if offset > 0 else None
    next_offset = offset + BANS_PAGE_SIZE if has_next else None
    await call.message.answer(
        "\n".join(lines),
        reply_markup=admin_bans_kb(
            [u.id for u in banned],
            lang,
            prev_offset=prev_offset,
            next_offset=next_offset,
        ),
    )
    await safe_answer(call)


@router.callback_query(F.data == "admin:bans")
async def admin_bans(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    await _send_bans_page(call, session, offset=0)


@router.callback_query(F.data.startswith("admin_bans_page:"))
async def admin_bans_page(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    try:
        offset = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await safe_answer(call)
        return
    await _send_bans_page(call, session, offset=offset)


async def _send_chats_page(call: CallbackQuery, session: AsyncSession, offset: int) -> None:
    offset = max(0, offset)
    chats = await ChatRepository(session).list_recent(limit=CHATS_PAGE_SIZE + 1, offset=offset)
    has_next = len(chats) > CHATS_PAGE_SIZE
    chats = chats[:CHATS_PAGE_SIZE]
    if not chats:
        await call.message.answer("Больше чатов нет." if offset else "Чатов нет.")
        await safe_answer(call)
        return

    repo = UserRepository(session)
    lines = ["Последние чаты (включая закрытые):"]
    kb_items: list[tuple[int, bool]] = []
    for c in chats:
        u1 = await repo.get(c.user1_id)
        u2 = await repo.get(c.user2_id)
        label = f"{u1.roblox_nick if u1 else c.user1_id} ↔ {u2.roblox_nick if u2 else c.user2_id}"
        status = "активный" if c.status == "active" else "закрыт"
        lines.append(f"{c.id} ({status}): {label}")
        kb_items.append((c.id, c.status == "active"))

    lang = await _admin_lang(session, call.from_user.id)
    prev_offset = offset - CHATS_PAGE_SIZE if offset > 0 else None
    next_offset = offset + CHATS_PAGE_SIZE if has_next else None
    await call.message.answer(
        "\n".join(lines),
        reply_markup=admin_chats_kb(
            kb_items,
            lang,
            prev_offset=prev_offset,
            next_offset=next_offset,
        ),
    )
    await safe_answer(call)


async def _send_active_chats_page(call: CallbackQuery, session: AsyncSession, offset: int) -> None:
    offset = max(0, offset)
    chats = await ChatRepository(session).list_recent(
        limit=CHATS_PAGE_SIZE + 1,
        offset=offset,
        status="active",
    )
    has_next = len(chats) > CHATS_PAGE_SIZE
    chats = chats[:CHATS_PAGE_SIZE]
    if not chats:
        await call.message.answer(
            "Активных чатов нет." if offset == 0 else "Больше активных чатов нет."
        )
        await safe_answer(call)
        return

    repo = UserRepository(session)
    lines = ["Активные чаты:"]
    kb_items: list[tuple[int, bool]] = []
    for c in chats:
        u1 = await repo.get(c.user1_id)
        u2 = await repo.get(c.user2_id)
        label = f"{u1.roblox_nick if u1 else c.user1_id} ↔ {u2.roblox_nick if u2 else c.user2_id}"
        lines.append(f"{c.id}: {label}")
        kb_items.append((c.id, True))

    lang = await _admin_lang(session, call.from_user.id)
    prev_offset = offset - CHATS_PAGE_SIZE if offset > 0 else None
    next_offset = offset + CHATS_PAGE_SIZE if has_next else None
    await call.message.answer(
        "\n".join(lines),
        reply_markup=admin_chats_kb(
            kb_items,
            lang,
            prev_offset=prev_offset,
            next_offset=next_offset,
            page_callback_prefix="admin_active_chats_page",
        ),
    )
    await safe_answer(call)


@router.callback_query(F.data == "admin:active_chats")
async def admin_active_chats(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    await _send_active_chats_page(call, session, offset=0)


@router.callback_query(F.data.startswith("admin_active_chats_page:"))
async def admin_active_chats_page(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    try:
        offset = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await safe_answer(call)
        return
    await _send_active_chats_page(call, session, offset=offset)


@router.callback_query(F.data == "admin:chats")
async def admin_chats(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    await _send_chats_page(call, session, offset=0)


@router.callback_query(F.data.startswith("admin_chats_page:"))
async def admin_chats_page(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    try:
        offset = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await safe_answer(call)
        return
    await _send_chats_page(call, session, offset=offset)


@router.callback_query(F.data.startswith("admin_chat_history:"))
async def admin_chat_history(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    chat_id = int(call.data.split(":")[1])
    msgs = await MessageRepository(session).list_for_chat(chat_id, limit=20)
    if not msgs:
        await call.message.answer("История пуста.")
        await safe_answer(call)
        return
    repo = UserRepository(session)
    lines = []
    for m in reversed(msgs):
        sender = await repo.get(m.sender_id)
        name = sender.roblox_nick if sender else str(m.sender_id)
        body = m.text or f"[{m.content_type}]"
        lines.append(f"{name}: {body}")
    await call.message.answer("\n".join(lines))
    await safe_answer(call)


@router.callback_query(F.data.startswith("admin_chat_close:"))
async def admin_chat_close(call: CallbackQuery, session: AsyncSession, bot) -> None:
    if not _is_admin(call.from_user.id):
        return
    chat_id = int(call.data.split(":")[1])
    chat_repo = ChatRepository(session)
    chat = await chat_repo.get(chat_id)
    if not chat or chat.status != "active":
        await call.message.answer("Чат не найден или уже закрыт.")
        await safe_answer(call)
        return
    await chat_repo.close(chat_id, datetime.now(timezone.utc))
    for uid in (chat.user1_id, chat.user2_id):
        u = await UserRepository(session).get(uid)
        if u:
            u.state = "idle"
            u.active_chat_id = None
        lang_u = u.language if u else "ru"
        try:
            await bot.send_message(uid, "Чат закрыт администратором.", reply_markup=main_menu_kb(lang_u))
        except Exception:
            pass
    await session.commit()
    await call.message.answer("Чат закрыт.")
    await safe_answer(call)


@router.callback_query(F.data == "admin:reports")
async def admin_reports(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    reports = await ReportRepository(session).list_recent(20)
    if not reports:
        await call.message.answer("Жалоб нет.")
        await safe_answer(call)
        return
    lines = [f"{r.id}: {r.reporter_id} → {r.target_id} ({r.reason})" for r in reports]
    lang = await _admin_lang(session, call.from_user.id)
    await call.message.answer(
        "Последние жалобы:\n" + "\n".join(lines),
        reply_markup=admin_reports_kb([r.id for r in reports], lang),
    )
    await safe_answer(call)


@router.callback_query(F.data.startswith("admin_report:"))
async def admin_report_detail(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    report_id = int(call.data.split(":")[1])
    rep = await ReportRepository(session).get(report_id)
    if not rep:
        await call.message.answer("Жалоба не найдена.")
        await safe_answer(call)
        return
    repo = UserRepository(session)
    reporter = await repo.get(rep.reporter_id)
    target = await repo.get(rep.target_id)
    text = (
        f"Жалоба #{rep.id}\n"
        f"От: {reporter.roblox_nick if reporter else rep.reporter_id}\n"
        f"На: {target.roblox_nick if target else rep.target_id}\n"
        f"Причина: {rep.reason}\n"
        f"Чат: {rep.chat_id or '-'}\n"
        f"Время: {rep.created_at:%Y-%m-%d %H:%M} UTC"
    )
    lang = await _admin_lang(session, call.from_user.id)
    await call.message.answer(text, reply_markup=admin_users_actions_kb(rep.target_id, bool(target and target.is_banned), bool(target and target.active_chat_id), lang))
    await safe_answer(call)


@router.callback_query(F.data == "admin:games")
async def admin_games(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    limit = 50
    total = games_service.count()
    games = games_service.list(limit=limit)
    if not games or total == 0:
        text = "Список игр пуст."
    else:
        lines = [f"- {g['code']}: {games_service.label(str(g['code']), 'ru')} / {g['name_en']}" for g in games]
        suffix = f"\n\nПоказано: {len(games)} из {total}."
        text = "Игры/режимы (топ по популярности):\n" + "\n".join(lines) + suffix
    lang = await _admin_lang(session, call.from_user.id)
    await call.message.answer(text, reply_markup=admin_games_kb(lang))
    await safe_answer(call)


@router.callback_query(F.data == "admin_games:add")
async def admin_games_add(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminPanelStates.games_add_code)
    await call.message.answer("Введи код игры (латиницей, без пробелов):")
    await safe_answer(call)


@router.message(AdminPanelStates.games_add_code)
async def admin_games_add_code(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    code = (message.text or "").strip()
    if not code:
        await message.answer("Код не может быть пустым.")
        return
    await state.update_data(game_code=code)
    await state.set_state(AdminPanelStates.games_add_names)
    await message.answer("Введи названия в формате: name_ru | name_en")


@router.message(AdminPanelStates.games_add_names)
async def admin_games_add_names(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    code = data["game_code"]
    raw = (message.text or "")
    if "|" not in raw:
        await message.answer("Формат: name_ru | name_en")
        return
    name_ru, name_en = [p.strip() for p in raw.split("|", 1)]
    games_service.add(code, name_ru, name_en)
    await state.clear()
    await message.answer("Добавлено. /admin чтобы открыть панель.")


@router.callback_query(F.data == "admin_games:remove")
async def admin_games_remove(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminPanelStates.games_remove_code)
    await call.message.answer("Введи код игры для удаления:")
    await safe_answer(call)


@router.message(AdminPanelStates.games_remove_code)
async def admin_games_remove_code(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    code = (message.text or "").strip()
    if games_service.remove(code):
        await message.answer("Удалено.")
    else:
        await message.answer("Код не найден.")
    await state.clear()


@router.callback_query(F.data == "admin_games:reload")
async def admin_games_reload(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        return
    games_service.load()
    await call.message.answer("Список игр обновлён.")
    await safe_answer(call)


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    if settings.main_admin_id and call.from_user.id != settings.main_admin_id:
        await safe_answer(call)
        return
    await state.set_state(BroadcastStates.text)
    await call.message.answer("Введи текст рассылки:")
    await safe_answer(call)


@router.callback_query(F.data == "admin:reengage")
async def admin_reengage(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    lang = await _admin_lang(session, call.from_user.id)
    await call.message.answer("Реэнгейджмент:", reply_markup=admin_reengage_kb(lang))
    await safe_answer(call)


@router.callback_query(F.data == "admin_reengage:run")
async def admin_reengage_run(call: CallbackQuery, session: AsyncSession, bot) -> None:
    if not _is_admin(call.from_user.id):
        return
    service = ReengageService(bot)
    await service._run_check()
    await call.message.answer("Проверка выполнена.")
    await safe_answer(call)


@router.callback_query(F.data == "admin_reengage:stats")
async def admin_reengage_stats(call: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(call.from_user.id):
        return
    now = datetime.now(timezone.utc)
    older_than = now - timedelta(hours=settings.reengage_after_hours)
    last_sent_before = now - timedelta(hours=settings.reengage_after_hours)
    candidates = await UserRepository(session).list_inactive(older_than, last_sent_before)
    last24 = now - timedelta(hours=24)
    sent24 = await session.scalar(
        select(func.count()).select_from(User).where(User.last_reengage_sent_at >= last24)
    )
    text = f"Кандидатов на напоминание: {len(candidates)}\nНапоминаний за 24ч: {sent24}"
    await call.message.answer(text)
    await safe_answer(call)
