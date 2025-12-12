from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.browse import browse_filters_kb, browse_nav_kb
from app.keyboards.offers import direct_request_kb
from app.keyboards.selection import language_kb, modes_kb
from app.models.user import User
from app.repositories.block_repo import BlockRepository
from app.repositories.offer_repo import OfferRepository
from app.repositories.user_repo import UserRepository
from app.utils.cards import format_profile
from app.utils.guards import ensure_registered_call, ensure_registered_message
from app.utils.i18n import t
from app.utils.states import BrowseFilterStates
from app.utils.tg import safe_answer, safe_edit_reply_markup

router = Router()


def _parse_range(text: str) -> tuple[int, int] | None:
    text = text.replace(" ", "").replace("–", "-").replace("—", "-")
    if "-" not in text:
        return None
    try:
        a, b = text.split("-", 1)
        return int(a), int(b)
    except ValueError:
        return None


async def _get_filtered(session: AsyncSession, viewer: User, filters: dict) -> list[User]:
    block_repo = BlockRepository(session)
    blocked_ids = await block_repo.list_for_user(viewer.id)

    stmt = select(User).where(User.id != viewer.id, User.is_banned.is_(False))
    if blocked_ids:
        stmt = stmt.where(User.id.not_in(blocked_ids))

    if filters.get("language"):
        stmt = stmt.where(User.language == filters["language"])
    if filters.get("min_age") is not None:
        stmt = stmt.where(User.age >= filters["min_age"])
    if filters.get("max_age") is not None:
        stmt = stmt.where(User.age <= filters["max_age"])

    users = list((await session.scalars(stmt)).all())
    if filters.get("modes"):
        req_modes = set(filters["modes"])
        users = [u for u in users if req_modes & set(u.modes or [])]
    return users


async def _show(
    viewer_id: int,
    session: AsyncSession,
    state: FSMContext,
    bot,
    delete_prev: CallbackQuery | None = None,
) -> None:
    viewer = await UserRepository(session).get(viewer_id)
    if not viewer:
        return
    data = await state.get_data()
    filters = data.get("filters") or {}
    index = int(data.get("index") or 0)
    users = await _get_filtered(session, viewer, filters)
    lang = viewer.language

    if not users:
        await bot.send_message(viewer_id, "Нет подходящих игроков.", reply_markup=browse_filters_kb(lang))
        return

    if index >= len(users):
        index = 0
    target = users[index]

    if delete_prev:
        try:
            await delete_prev.message.delete()
        except Exception:
            pass

    await bot.send_message(
        viewer_id,
        format_profile(target, lang),
        reply_markup=browse_nav_kb(target.id, index, len(users), lang),
    )
    await state.update_data(filters=filters, index=index)


@router.message(Command("browse"))
async def browse_cmd(message: Message, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    await state.update_data(filters={}, index=0)
    await _show(user.id, session, state, bot)


@router.callback_query(F.data == "go:browse")
async def go_browse_cb(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await state.update_data(filters={}, index=0)
    await _show(user.id, session, state, bot, delete_prev=call)
    await safe_answer(call)


@router.callback_query(F.data.in_({"browse_prev", "browse_next"}))
async def browse_nav_cb(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    data = await state.get_data()
    index = int(data.get("index") or 0)
    users = await _get_filtered(session, user, data.get("filters") or {})
    if not users:
        await safe_answer(call)
        return
    if call.data == "browse_prev":
        index = max(0, index - 1)
    else:
        index = min(len(users) - 1, index + 1)
    await state.update_data(index=index)
    await _show(user.id, session, state, bot, delete_prev=call)
    await safe_answer(call)


@router.callback_query(F.data == "browse_filters")
async def browse_filters_cb(call: CallbackQuery, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await call.message.answer("Фильтры:", reply_markup=browse_filters_kb(user.language))
    await safe_answer(call)


@router.callback_query(F.data == "browse_set_lang")
async def browse_set_lang(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    filters = (await state.get_data()).get("filters") or {}
    selected = filters.get("language") or "any"
    await call.message.answer(
        "Выбери язык партнёра:",
        reply_markup=language_kb("browse_lang", user.language, selected=selected, include_any=True),
    )
    await safe_answer(call)


@router.callback_query(F.data.startswith("browse_lang:"))
async def browse_lang_pick(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    code = call.data.split(":")[1]
    data = await state.get_data()
    filters = data.get("filters") or {}
    filters["language"] = None if code == "any" else code
    await state.update_data(filters=filters, index=0)
    await _show(user.id, session, state, bot, delete_prev=call)
    await safe_answer(call)


@router.callback_query(F.data == "browse_set_age")
async def browse_set_age(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await state.set_state(BrowseFilterStates.age_range)
    await call.message.answer("Введи диапазон возраста партнёра, например 12-18:")
    await safe_answer(call)


@router.message(BrowseFilterStates.age_range)
async def browse_age_range(message: Message, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    parsed = _parse_range(message.text or "")
    if not parsed:
        await message.answer("Формат: min-max")
        return
    min_age, max_age = parsed
    if min_age > max_age:
        min_age, max_age = max_age, min_age
    min_age = max(8, min_age)
    max_age = min(99, max_age)
    data = await state.get_data()
    filters = data.get("filters") or {}
    filters["min_age"] = min_age
    filters["max_age"] = max_age
    await state.update_data(filters=filters, index=0)
    await state.set_state(None)
    await _show(user.id, session, state, bot)


@router.callback_query(F.data == "browse_set_modes")
async def browse_set_modes(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    data = await state.get_data()
    filters = data.get("filters") or {}
    selected = filters.get("modes") or []
    await state.update_data(filters=filters, modes_selected=selected, modes_query=None)
    await state.set_state(BrowseFilterStates.modes)
    sent = await call.message.answer(
        "Выбери режимы:" if user.language == "ru" else "Choose modes:",
        reply_markup=modes_kb("browse_mode", user.language, selected),
    )
    await state.update_data(modes_msg_id=sent.message_id)
    await safe_answer(call)


@router.message(BrowseFilterStates.modes)
async def browse_modes_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    if not message.text:
        return
    query = message.text.strip()
    if not query or query.startswith("/"):
        return

    if query.casefold() in {"сброс", "очистить", "clear", "reset"}:
        query = ""

    data = await state.get_data()
    selected: list[str] = data.get("modes_selected") or []
    prev_msg_id = data.get("modes_msg_id")

    await state.update_data(modes_query=query or None)

    if prev_msg_id:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=int(prev_msg_id),
                reply_markup=None,
            )
        except Exception:
            pass

    text = "Выбери режимы:" if user.language == "ru" else "Choose modes:"
    text += f"\n\n🔍 Поиск: <code>{html.escape(query)}</code>" if query else ""
    sent = await message.answer(
        text,
        reply_markup=modes_kb("browse_mode", user.language, selected, query=query or None),
    )
    await state.update_data(modes_msg_id=sent.message_id)


@router.callback_query(F.data.startswith("browse_mode:"))
async def browse_modes_pick(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    code = call.data.split(":")[1]
    data = await state.get_data()
    filters = data.get("filters") or {}
    selected: list[str] = data.get("modes_selected") or []
    query = data.get("modes_query")

    await state.update_data(modes_msg_id=call.message.message_id)

    if code == "__noop":
        await safe_answer(call)
        return

    if code == "__search":
        await safe_answer(
            call,
            "Напиши название режима сообщением для поиска."
            if user.language == "ru"
            else "Type mode name as a message to search.",
        )
        return

    if code == "__clear":
        await state.update_data(modes_query=None)
        await safe_edit_reply_markup(call.message, reply_markup=modes_kb("browse_mode", user.language, selected, query=None))
        await safe_answer(call)
        return

    if code == "done":
        filters["modes"] = selected
        await state.update_data(filters=filters, index=0)
        await state.set_state(None)
        await _show(user.id, session, state, bot, delete_prev=call)
        await safe_answer(call)
        return

    if code in selected:
        selected.remove(code)
    else:
        if len(selected) >= 5:
            await safe_answer(call, "Максимум 5.")
            return
        selected.append(code)

    await state.update_data(modes_selected=selected)
    await safe_edit_reply_markup(call.message, reply_markup=modes_kb("browse_mode", user.language, selected, query=query))
    await safe_answer(call)


@router.callback_query(F.data == "browse_reset")
async def browse_reset(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await state.update_data(filters={}, index=0)
    await _show(user.id, session, state, bot, delete_prev=call)
    await safe_answer(call)


@router.callback_query(F.data == "browse_back")
async def browse_back(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await _show(user.id, session, state, bot, delete_prev=call)
    await safe_answer(call)


@router.callback_query(F.data.startswith("browse_offer:"))
async def browse_offer(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    target_id = int(call.data.split(":")[1])
    if await BlockRepository(session).is_blocked_pair(user.id, target_id):
        await safe_answer(call, "Вы не можете предложить чат этому пользователю.")
        return

    target = await UserRepository(session).get(target_id)
    if not target or target.is_banned:
        await safe_answer(call, "Пользователь недоступен.")
        return

    offer_repo = OfferRepository(session)
    offer = await offer_repo.find_between(user.id, target_id)
    if not offer or offer.status not in {"pending", "offered1", "offered2"}:
        offer = await offer_repo.create(user.id, target_id, None, None)
        offer.status = "offered1"

    user.state = "matching"
    user.active_offer_id = offer.id
    target.state = "matching"
    target.active_offer_id = offer.id

    await session.commit()

    await bot.send_message(
        target.id,
        t(target.language, "offer_received") + "\n\n" + format_profile(user, target.language),
        reply_markup=direct_request_kb(offer.id, target.language),
    )
    await call.message.answer(t(user.language, "offer_sent"))
    await safe_answer(call)
