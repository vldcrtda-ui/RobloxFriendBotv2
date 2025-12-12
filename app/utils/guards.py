from __future__ import annotations

from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.menu import main_menu_kb
from app.repositories.user_repo import UserRepository
from app.utils.i18n import t


async def get_user(session: AsyncSession, user_id: int):
    return await UserRepository(session).get(user_id)


async def ensure_registered_message(message: Message, session: AsyncSession):
    user = await get_user(session, message.from_user.id)
    if not user:
        await message.answer(t("ru", "not_registered"))
        return None
    return user


async def ensure_registered_call(call: CallbackQuery, session: AsyncSession):
    user = await get_user(session, call.from_user.id)
    if not user:
        await call.message.answer(t("ru", "not_registered"), reply_markup=main_menu_kb("ru"))
        await call.answer()
        return None
    return user

