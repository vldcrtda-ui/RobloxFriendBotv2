from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.keyboards.chat import active_chat_kb, report_reasons_kb
from app.keyboards.menu import main_menu_kb
from app.keyboards.offers import direct_request_kb, match_actions_kb, search_cancel_kb
from app.keyboards.selection import confirm_kb
from app.repositories.chat_repo import ChatRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.offer_repo import OfferRepository
from app.repositories.report_repo import ReportRepository
from app.repositories.user_repo import UserRepository
from app.services.matching import matching_service
from app.services.offers import offer_service
from app.utils.cards import format_profile
from app.utils.guards import ensure_registered_call, ensure_registered_message
from app.utils.i18n import t
from app.utils.states import RandomChatStates
from app.utils.tg import safe_answer

router = Router()


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


@router.message(Command("chat"))
async def random_chat_cmd(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    if user.state == "chatting":
        await message.answer("Вы уже в чате. /exit_chat чтобы выйти.")
        return
    await state.set_state(RandomChatStates.confirm)
    await message.answer(
        "Начать рандом‑чат?",
        reply_markup=confirm_kb("random_chat_start", "random_chat_cancel", user.language),
    )


@router.callback_query(F.data == "go:chat")
async def go_chat_cb(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await state.set_state(RandomChatStates.confirm)
    await call.message.answer(
        "Начать рандом‑чат?",
        reply_markup=confirm_kb("random_chat_start", "random_chat_cancel", user.language),
    )
    await safe_answer(call)


@router.callback_query(RandomChatStates.confirm, F.data == "random_chat_start")
async def random_chat_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await state.clear()
    _, offer_id = await matching_service.enqueue(session, user.id, None, 8, 99, [])
    await session.commit()
    if offer_id:
        await _notify_offer(session, bot, offer_id)
    else:
        await call.message.answer(t(user.language, "searching"), reply_markup=search_cancel_kb(user.language))
    await safe_answer(call)


@router.callback_query(RandomChatStates.confirm, F.data == "random_chat_cancel")
async def random_chat_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("Отменено.")
    await safe_answer(call)


@router.message(Command("exit_chat"))
async def exit_chat_cmd(message: Message, session: AsyncSession, bot) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    chat = await ChatRepository(session).get_active_for_user(user.id)
    if not chat:
        await message.answer("Активного чата нет.")
        return

    await offer_service.close_chat_for_user(session, user.id)
    await session.commit()

    for uid in (chat.user1_id, chat.user2_id):
        u = await UserRepository(session).get(uid)
        lang = u.language if u else "ru"
        await bot.send_message(uid, t(lang, "chat_ended"), reply_markup=main_menu_kb(lang))


@router.callback_query(F.data == "chat_end")
async def chat_end_cb(call: CallbackQuery, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    chat = await ChatRepository(session).get_active_for_user(user.id)
    if not chat:
        await safe_answer(call)
        return
    await offer_service.close_chat_for_user(session, user.id)
    await session.commit()
    for uid in (chat.user1_id, chat.user2_id):
        u = await UserRepository(session).get(uid)
        lang = u.language if u else "ru"
        await bot.send_message(uid, t(lang, "chat_ended"), reply_markup=main_menu_kb(lang))
    await safe_answer(call)


@router.callback_query(F.data == "chat_block")
async def chat_block_cb(call: CallbackQuery, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    chat = await ChatRepository(session).get_active_for_user(user.id)
    if not chat:
        await safe_answer(call)
        return
    partner_id = chat.user2_id if chat.user1_id == user.id else chat.user1_id
    offer = await OfferRepository(session).find_between(user.id, partner_id)
    if offer:
        await offer_service.block_pair(session, offer.id, user.id)
    await offer_service.close_chat_for_user(session, user.id)
    await session.commit()
    await bot.send_message(user.id, t(user.language, "blocked"), reply_markup=main_menu_kb(user.language))
    await bot.send_message(partner_id, "Вы были заблокированы собеседником.")
    await safe_answer(call)


@router.callback_query(F.data == "chat_report")
async def chat_report_cb(call: CallbackQuery, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await call.message.answer("Выбери причину:", reply_markup=report_reasons_kb(user.language))
    await safe_answer(call)


@router.callback_query(F.data == "report_cancel")
async def report_cancel(call: CallbackQuery) -> None:
    await safe_answer(call)


@router.callback_query(F.data.startswith("report:"))
async def report_reason(call: CallbackQuery, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    reason = call.data.split(":")[1]
    chat = await ChatRepository(session).get_active_for_user(user.id)
    if not chat:
        await safe_answer(call)
        return
    partner_id = chat.user2_id if chat.user1_id == user.id else chat.user1_id
    await ReportRepository(session).add(user.id, partner_id, chat.id, reason, None)
    await session.commit()

    for admin_id in settings.admin_id_set:
        try:
            await bot.send_message(
                admin_id,
                f"Жалоба от {user.id} на {partner_id}\nПричина: {reason}\nЧат: {chat.id}",
            )
        except Exception:
            pass

    await call.message.answer("Жалоба отправлена.")
    await safe_answer(call)


@router.callback_query(F.data.startswith("offer_chat:"))
async def offer_chat_cb(call: CallbackQuery, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    offer_id = int(call.data.split(":")[1])
    chat_id = await offer_service.propose_chat(session, offer_id, user.id)
    await session.commit()

    offer = await OfferRepository(session).get(offer_id)
    if not offer:
        await safe_answer(call)
        return

    other_id = offer.user2_id if user.id == offer.user1_id else offer.user1_id
    other_user = await UserRepository(session).get(other_id)

    if chat_id:
        for uid in (offer.user1_id, offer.user2_id):
            u = await UserRepository(session).get(uid)
            lang = u.language if u else "ru"
            await bot.send_message(uid, t(lang, "chat_started"), reply_markup=active_chat_kb(lang))
    else:
        await bot.send_message(
            other_id,
            t(other_user.language if other_user else "ru", "offer_received")
            + "\n\n"
            + format_profile(user, other_user.language if other_user else "ru"),
            reply_markup=direct_request_kb(offer_id, other_user.language if other_user else "ru"),
        )
        await bot.send_message(user.id, t(user.language, "offer_sent"))

    await safe_answer(call)


@router.callback_query(F.data.startswith("offer_skip:"))
async def offer_skip_cb(call: CallbackQuery, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    offer_id = int(call.data.split(":")[1])
    await offer_service.decline(session, offer_id, user.id)
    await session.commit()

    offer = await OfferRepository(session).get(offer_id)
    if not offer:
        await safe_answer(call)
        return

    for uid in (offer.user1_id, offer.user2_id):
        u = await UserRepository(session).get(uid)
        if not u or not u.last_search:
            continue
        filters = u.last_search
        _, new_offer = await matching_service.enqueue(
            session,
            u.id,
            filters.get("language"),
            filters.get("min_age", 8),
            filters.get("max_age", 99),
            filters.get("modes") or [],
        )
        await session.commit()
        if new_offer:
            await _notify_offer(session, bot, new_offer)
        else:
            await bot.send_message(u.id, t(u.language, "searching"), reply_markup=search_cancel_kb(u.language))

    await safe_answer(call)


@router.callback_query(F.data.startswith("offer_block:"))
async def offer_block_cb(call: CallbackQuery, session: AsyncSession, bot) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    offer_id = int(call.data.split(":")[1])
    target_id = await offer_service.block_pair(session, offer_id, user.id)
    await session.commit()

    await bot.send_message(user.id, t(user.language, "blocked"), reply_markup=main_menu_kb(user.language))
    if target_id:
        await bot.send_message(target_id, "Вы были заблокированы.")
    await safe_answer(call)


async def _relay(message: Message, session: AsyncSession, bot) -> None:
    user = await UserRepository(session).get(message.from_user.id)
    if not user or user.state != "chatting":
        return

    chat = await ChatRepository(session).get_active_for_user(user.id)
    if not chat:
        return

    partner_id = chat.user2_id if chat.user1_id == user.id else chat.user1_id
    try:
        await bot.copy_message(partner_id, message.chat.id, message.message_id)
    except Exception:
        return

    content_type = message.content_type
    text = (
        message.text
        if content_type == "text"
        else (message.caption if getattr(message, "caption", None) else None)
    )
    file_id = None
    if content_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id
    elif hasattr(message, content_type):
        media = getattr(message, content_type)
        if hasattr(media, "file_id"):
            file_id = media.file_id

    await MessageRepository(session).add(chat.id, user.id, content_type, text=text, file_id=file_id)
    await session.commit()


@router.message(F.text & ~F.text.startswith("/"))
async def relay_text_messages(message: Message, session: AsyncSession, bot) -> None:
    await _relay(message, session, bot)


@router.message(~F.text)
async def relay_nontext_messages(message: Message, session: AsyncSession, bot) -> None:
    await _relay(message, session, bot)
