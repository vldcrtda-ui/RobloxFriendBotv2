from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.keyboards.admin import broadcast_confirm_kb
from app.keyboards.menu import main_menu_kb
from app.models.chat import ChatSession
from app.models.search import SearchRequest
from app.models.user import User
from app.repositories.chat_repo import ChatRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.user_repo import UserRepository
from app.services.games import games_service
from app.utils.states import BroadcastStates
from app.utils.tg import safe_answer

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_set


@router.message(Command("metrics"))
async def metrics_cmd(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
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
    await message.answer(text)


@router.message(Command("ban"))
async def ban_cmd(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Использование: /ban &lt;id|nick&gt; &lt;days|0&gt; [reason]")
        return
    target_raw = parts[1]
    days = int(parts[2])
    reason = parts[3] if len(parts) > 3 else None

    repo = UserRepository(session)
    target = await (repo.get(int(target_raw)) if target_raw.isdigit() else repo.get_by_nick(target_raw))
    if not target:
        await message.answer("Пользователь не найден.")
        return

    until = None if days == 0 else datetime.now(timezone.utc) + timedelta(days=days)
    await repo.set_ban(target.id, until, reason)
    await session.commit()
    await message.answer(f"Бан выдан пользователю {target.id}.")


@router.message(Command("unban"))
async def unban_cmd(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /unban &lt;id|nick&gt;")
        return
    target_raw = parts[1]
    repo = UserRepository(session)
    target = await (repo.get(int(target_raw)) if target_raw.isdigit() else repo.get_by_nick(target_raw))
    if not target:
        await message.answer("Не найден.")
        return
    await repo.clear_ban(target.id)
    await session.commit()
    await message.answer("Разбанено.")


@router.message(Command("banstatus"))
async def banstatus_cmd(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    stmt = select(User).where(User.is_banned.is_(True))
    users = list((await session.scalars(stmt)).all())
    if not users:
        await message.answer("Банов нет.")
        return
    lines = []
    for u in users:
        lines.append(f"- {u.id} {u.roblox_nick} до {u.ban_until or '∞'}")
    await message.answer("\n".join(lines))


@router.message(Command("active_chats"))
async def active_chats_cmd(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    chats = await ChatRepository(session).list_active()
    if not chats:
        await message.answer("Активных чатов нет.")
        return
    repo = UserRepository(session)
    lines = []
    for c in chats:
        u1 = await repo.get(c.user1_id)
        u2 = await repo.get(c.user2_id)
        lines.append(
            f"{c.id}: {u1.roblox_nick if u1 else c.user1_id} ↔ {u2.roblox_nick if u2 else c.user2_id}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("chats"))
async def chats_cmd(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    limit = 20
    if len(parts) > 1:
        if not parts[1].isdigit():
            await message.answer("Использование: /chats [limit]")
            return
        limit = max(1, min(100, int(parts[1])))

    chats = await ChatRepository(session).list_recent(limit=limit)
    if not chats:
        await message.answer("Чатов нет.")
        return

    repo = UserRepository(session)
    lines = []
    for c in chats:
        u1 = await repo.get(c.user1_id)
        u2 = await repo.get(c.user2_id)
        status = "active" if c.status == "active" else "closed"
        lines.append(
            f"{c.id} ({status}): {u1.roblox_nick if u1 else c.user1_id} ↔ {u2.roblox_nick if u2 else c.user2_id}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("chat_history"))
async def chat_history_cmd(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Использование: /chat_history &lt;chat_id&gt;")
        return
    chat_id = int(parts[1])
    msgs = await MessageRepository(session).list_for_chat(chat_id, limit=20)
    if not msgs:
        await message.answer("История пуста.")
        return
    repo = UserRepository(session)
    lines = []
    for m in reversed(msgs):
        sender = await repo.get(m.sender_id)
        name = sender.roblox_nick if sender else str(m.sender_id)
        body = m.text or f"[{m.content_type}]"
        lines.append(f"{name}: {body}")
    await message.answer("\n".join(lines))


@router.message(Command("broadcast"))
async def broadcast_cmd(message: Message, state: FSMContext) -> None:
    if settings.main_admin_id and message.from_user.id != settings.main_admin_id:
        return
    await state.set_state(BroadcastStates.text)
    await message.answer("Введи текст рассылки:")


@router.message(BroadcastStates.text)
async def broadcast_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text)
    await state.set_state(BroadcastStates.confirm)
    await message.answer("Отправить всем?", reply_markup=broadcast_confirm_kb("ru"))


@router.callback_query(BroadcastStates.confirm, F.data.in_({"broadcast_yes", "broadcast_no"}))
async def broadcast_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    if settings.main_admin_id and call.from_user.id != settings.main_admin_id:
        await safe_answer(call)
        return
    data = await state.get_data()
    text = data.get("text") or ""
    await state.clear()
    if call.data == "broadcast_no":
        await call.message.answer("Отменено.")
        await safe_answer(call)
        return

    users = list((await session.scalars(select(User))).all())
    sent = 0
    for u in users:
        try:
            await bot.send_message(u.id, text, reply_markup=main_menu_kb(u.language))
            sent += 1
        except Exception:
            continue
    await call.message.answer(f"Готово. Отправлено: {sent}")
    await safe_answer(call)


@router.message(Command("games"))
async def games_cmd(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    games = games_service.list()
    if not games:
        await message.answer("Список игр пуст.")
        return
    lines = [f"- {g['code']}: {g['name_ru']} / {g['name_en']}" for g in games]
    lines.append("\nДобавить: /games_add &lt;code&gt; &lt;name_ru&gt; | &lt;name_en&gt;")
    lines.append("Удалить: /games_remove &lt;code&gt;")
    await message.answer("\n".join(lines))


@router.message(Command("games_add"))
async def games_add_cmd(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").split(maxsplit=2)
    if len(raw) < 3 or "|" not in raw[2]:
        await message.answer("Использование: /games_add &lt;code&gt; &lt;name_ru&gt; | &lt;name_en&gt;")
        return
    code = raw[1]
    name_ru, name_en = [p.strip() for p in raw[2].split("|", 1)]
    games_service.add(code, name_ru, name_en)
    await message.answer("Добавлено.")


@router.message(Command("games_remove"))
async def games_remove_cmd(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) < 2:
        await message.answer("Использование: /games_remove &lt;code&gt;")
        return
    code = raw[1].strip()
    if games_service.remove(code):
        await message.answer("Удалено.")
    else:
        await message.answer("Не найдено.")
