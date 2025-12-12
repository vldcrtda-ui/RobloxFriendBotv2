from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.menu import main_menu_kb
from app.keyboards.selection import language_kb, modes_kb, skip_kb
from app.repositories.user_repo import UserRepository
from app.utils.i18n import t
from app.utils.states import RegistrationStates
from app.utils.tg import safe_answer, safe_edit_reply_markup, safe_edit_text

router = Router()

NICK_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, session: AsyncSession) -> None:
    repo = UserRepository(session)
    user = await repo.get(message.from_user.id)
    if user:
        await state.clear()
        await message.answer(t(user.language, "welcome_back"), reply_markup=main_menu_kb(user.language))
        return

    await state.set_state(RegistrationStates.nick)
    await message.answer(t("ru", "welcome_new") + "\n" + t("ru", "ask_nick"))


@router.message(RegistrationStates.nick)
async def reg_nick(message: Message, state: FSMContext, session: AsyncSession) -> None:
    nick = (message.text or "").strip()
    if not NICK_RE.match(nick):
        await message.answer("Ник должен быть 3–20 символов (латиница/цифры/_)")
        return

    repo = UserRepository(session)
    if await repo.is_nick_taken(nick):
        await message.answer(t("ru", "nick_taken"))
        return

    await state.update_data(roblox_nick=nick)
    await state.set_state(RegistrationStates.age)
    await message.answer(t("ru", "ask_age"))


@router.message(RegistrationStates.age)
async def reg_age(message: Message, state: FSMContext) -> None:
    try:
        age = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите число.")
        return
    if not 8 <= age <= 99:
        await message.answer("Возраст должен быть 8–99.")
        return
    await state.update_data(age=age)
    await state.set_state(RegistrationStates.language)
    await message.answer(t("ru", "ask_lang"), reply_markup=language_kb("reg_lang", "ru"))


@router.callback_query(RegistrationStates.language, F.data.startswith("reg_lang:"))
async def reg_lang(call: CallbackQuery, state: FSMContext) -> None:
    lang = call.data.split(":")[1]
    await state.update_data(language=lang, modes=[])
    await state.set_state(RegistrationStates.modes)
    await safe_edit_text(call.message, t(lang, "ask_modes"), reply_markup=modes_kb("reg_mode", lang, []))
    await safe_answer(call)


@router.callback_query(RegistrationStates.modes, F.data.startswith("reg_mode:"))
async def reg_modes(call: CallbackQuery, state: FSMContext) -> None:
    code = call.data.split(":")[1]
    data = await state.get_data()
    lang = data.get("language", "ru")
    selected: list[str] = data.get("modes", [])

    if code == "done":
        if not selected:
            await safe_answer(call, "Выбери хотя бы один режим.")
            return
        await state.set_state(RegistrationStates.bio)
        await safe_edit_text(call.message, t(lang, "ask_bio"))
        await safe_answer(call)
        return

    if code in selected:
        selected.remove(code)
    else:
        if len(selected) >= 5:
            await safe_answer(call, "Максимум 5 режимов.")
            return
        selected.append(code)

    await state.update_data(modes=selected)
    await safe_edit_reply_markup(call.message, reply_markup=modes_kb("reg_mode", lang, selected))
    await safe_answer(call)


@router.message(RegistrationStates.bio)
async def reg_bio(message: Message, state: FSMContext) -> None:
    bio = (message.text or "").strip()
    if len(bio) > 200:
        bio = bio[:200]
    await state.update_data(bio=bio)
    data = await state.get_data()
    lang = data.get("language", "ru")
    await state.set_state(RegistrationStates.avatar)
    await message.answer(t(lang, "ask_avatar"), reply_markup=skip_kb("reg_avatar:skip", lang))


@router.callback_query(RegistrationStates.avatar, F.data == "reg_avatar:skip")
async def reg_avatar_skip(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot) -> None:
    await _finish_registration(call.message.chat.id, None, state, session, bot)
    await safe_answer(call)


@router.message(RegistrationStates.avatar, F.photo)
async def reg_avatar_photo(message: Message, state: FSMContext, session: AsyncSession, bot) -> None:
    file_id = message.photo[-1].file_id
    await _finish_registration(message.chat.id, file_id, state, session, bot)


async def _finish_registration(
    chat_id: int,
    avatar_file_id: str | None,
    state: FSMContext,
    session: AsyncSession,
    bot,
) -> None:
    data = await state.get_data()
    lang = data.get("language", "ru")
    repo = UserRepository(session)
    await repo.create(
        user_id=chat_id,
        roblox_nick=data["roblox_nick"],
        age=data["age"],
        language=lang,
        modes=data.get("modes", []),
        bio=data.get("bio", ""),
        avatar_file_id=avatar_file_id,
    )
    await session.commit()
    await state.clear()
    await bot.send_message(chat_id, t(lang, "reg_done"), reply_markup=main_menu_kb(lang))
