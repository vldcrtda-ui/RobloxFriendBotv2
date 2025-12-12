from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.menu import main_menu_kb
from app.keyboards.offers import match_actions_kb, search_cancel_kb
from app.keyboards.selection import confirm_kb, language_kb, modes_kb
from app.repositories.offer_repo import OfferRepository
from app.repositories.user_repo import UserRepository
from app.services.matching import matching_service
from app.utils.cards import format_profile
from app.utils.guards import ensure_registered_call, ensure_registered_message
from app.utils.i18n import t
from app.utils.states import SearchStates
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


async def _notify_offer(session: AsyncSession, bot, offer_id: int) -> None:
    offer = await OfferRepository(session).get(offer_id)
    if not offer:
        return
    user_repo = UserRepository(session)
    u1 = await user_repo.get(offer.user1_id)
    u2 = await user_repo.get(offer.user2_id)
    if not u1 or not u2:
        return

    await bot.send_message(
        u1.id,
        t(u1.language, "match_found") + "\n\n" + format_profile(u2, u1.language),
        reply_markup=match_actions_kb(offer_id, u1.language),
    )
    await bot.send_message(
        u2.id,
        t(u2.language, "match_found") + "\n\n" + format_profile(u1, u2.language),
        reply_markup=match_actions_kb(offer_id, u2.language),
    )


@router.message(Command("search"))
async def search_cmd(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    await state.set_state(SearchStates.language)
    await message.answer(
        "Выбери язык партнёра:",
        reply_markup=language_kb("search_lang", user.language, include_any=True),
    )


@router.callback_query(F.data == "go:search")
async def go_search_cb(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await state.set_state(SearchStates.language)
    await call.message.answer(
        "Выбери язык партнёра:",
        reply_markup=language_kb("search_lang", user.language, include_any=True),
    )
    await safe_answer(call)


@router.callback_query(SearchStates.language, F.data.startswith("search_lang:"))
async def search_lang(call: CallbackQuery, state: FSMContext) -> None:
    code = call.data.split(":")[1]
    await state.update_data(language=None if code == "any" else code)
    await state.set_state(SearchStates.age_range)
    await call.message.answer("Введи диапазон возраста партнёра, например 12-18:")
    await safe_answer(call)


@router.message(SearchStates.age_range)
async def search_age(message: Message, state: FSMContext) -> None:
    parsed = _parse_range(message.text or "")
    if not parsed:
        await message.answer("Формат: min-max")
        return
    min_age, max_age = parsed
    if min_age > max_age:
        min_age, max_age = max_age, min_age
    min_age = max(8, min_age)
    max_age = min(99, max_age)
    await state.update_data(min_age=min_age, max_age=max_age, modes=[], modes_query=None)
    await state.set_state(SearchStates.modes)
    data = await state.get_data()
    lang = data.get("language") or "ru"
    sent = await message.answer(t(lang, "ask_modes"), reply_markup=modes_kb("search_mode", lang, []))
    await state.update_data(modes_msg_id=sent.message_id)


@router.message(SearchStates.modes)
async def search_modes_search(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    query = message.text.strip()
    if not query or query.startswith("/"):
        return

    if query.casefold() in {"сброс", "очистить", "clear", "reset"}:
        query = ""

    data = await state.get_data()
    lang = data.get("language") or "ru"
    selected: list[str] = data.get("modes", [])
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

    text = t(lang, "ask_modes")
    text += f"\n\n🔍 Поиск: <code>{html.escape(query)}</code>" if query else ""
    sent = await message.answer(text, reply_markup=modes_kb("search_mode", lang, selected, query=query or None))
    await state.update_data(modes_msg_id=sent.message_id)


@router.callback_query(SearchStates.modes, F.data.startswith("search_mode:"))
async def search_modes(call: CallbackQuery, state: FSMContext) -> None:
    code = call.data.split(":")[1]
    data = await state.get_data()
    lang = data.get("language") or "ru"
    selected: list[str] = data.get("modes", [])
    query = data.get("modes_query")

    await state.update_data(modes_msg_id=call.message.message_id)

    if code == "__noop":
        await safe_answer(call)
        return

    if code == "__search":
        await safe_answer(
            call,
            "Напиши название режима сообщением для поиска." if lang == "ru" else "Type mode name as a message to search.",
        )
        return

    if code == "__clear":
        await state.update_data(modes_query=None)
        await safe_edit_reply_markup(call.message, reply_markup=modes_kb("search_mode", lang, selected, query=None))
        await safe_answer(call)
        return

    if code == "done":
        await state.set_state(SearchStates.confirm)
        summary = (
            f"Язык: {data.get('language') or 'любой'}\n"
            f"Возраст: {data['min_age']}-{data['max_age']}\n"
            f"Режимы: {', '.join(selected) if selected else 'любые'}"
        )
        await call.message.answer(
            "Подтвердить поиск?\n" + summary,
            reply_markup=confirm_kb("search_start", "search_cancel", lang, yes_text="Начать", no_text="Отмена"),
        )
        await safe_answer(call)
        return

    if code in selected:
        selected.remove(code)
    else:
        if len(selected) >= 5:
            await safe_answer(call, "Максимум 5.")
            return
        selected.append(code)
    await state.update_data(modes=selected)
    await safe_edit_reply_markup(call.message, reply_markup=modes_kb("search_mode", lang, selected, query=query))
    await safe_answer(call)


@router.callback_query(SearchStates.confirm, F.data == "search_start")
async def search_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    data = await state.get_data()
    await state.clear()

    _, offer_id = await matching_service.enqueue(
        session,
        user.id,
        data.get("language"),
        data["min_age"],
        data["max_age"],
        data.get("modes") or [],
    )
    await session.commit()

    if offer_id:
        await _notify_offer(session, bot, offer_id)
    else:
        await call.message.answer(t(user.language, "searching"), reply_markup=search_cancel_kb(user.language))
    await safe_answer(call)


@router.callback_query(F.data == "search_cancel")
async def search_cancel(call: CallbackQuery, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await matching_service.cancel_search(session, user.id)
    await session.commit()
    await call.message.answer(t(user.language, "search_canceled"), reply_markup=main_menu_kb(user.language))
    await safe_answer(call)
