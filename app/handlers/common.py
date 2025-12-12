from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.menu import main_menu_kb
from app.repositories.user_repo import UserRepository
from app.services.matching import matching_service
from app.utils.i18n import t
from app.utils.tg import safe_answer

router = Router()


@router.callback_query(F.data == "noop")
async def noop_cb(call: CallbackQuery) -> None:
    await safe_answer(call)


@router.callback_query(F.data == "menu")
async def menu_cb(call: CallbackQuery, session: AsyncSession) -> None:
    user = await UserRepository(session).get(call.from_user.id)
    lang = user.language if user else "ru"
    await call.message.answer(t(lang, "menu_hint"), reply_markup=main_menu_kb(lang))
    await safe_answer(call)


@router.callback_query(F.data == "go:help")
async def go_help_cb(call: CallbackQuery, session: AsyncSession) -> None:
    user = await UserRepository(session).get(call.from_user.id)
    lang = user.language if user else "ru"
    await call.message.answer(t(lang, "help"), reply_markup=main_menu_kb(lang))
    await safe_answer(call)


@router.message(Command("help"))
async def help_cmd(message: Message, session: AsyncSession) -> None:
    user = await UserRepository(session).get(message.from_user.id)
    lang = user.language if user else "ru"
    await message.answer(t(lang, "help"), reply_markup=main_menu_kb(lang))


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    user = await UserRepository(session).get(message.from_user.id)
    lang = user.language if user else "ru"

    if user and user.state == "searching":
        await matching_service.cancel_search(session, user.id)
        await session.commit()
        await message.answer(t(lang, "search_canceled"), reply_markup=main_menu_kb(lang))
        return

    await message.answer(t(lang, "cancel"), reply_markup=main_menu_kb(lang))
