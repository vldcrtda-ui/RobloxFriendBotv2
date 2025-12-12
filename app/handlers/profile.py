from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.profile import profile_kb
from app.keyboards.selection import confirm_kb, language_kb, modes_kb, skip_kb
from app.repositories.block_repo import BlockRepository
from app.repositories.user_repo import UserRepository
from app.utils.cards import format_profile
from app.utils.guards import ensure_registered_call, ensure_registered_message
from app.utils.i18n import t
from app.utils.states import ProfileEditStates
from app.utils.tg import safe_answer, safe_edit_reply_markup

router = Router()

NICK_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


@router.message(Command("profile"))
async def profile_cmd(message: Message, session: AsyncSession) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    await message.answer(format_profile(user, user.language), reply_markup=profile_kb(user.language))


@router.callback_query(F.data == "go:profile")
async def go_profile_cb(call: CallbackQuery, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await call.message.answer(format_profile(user, user.language), reply_markup=profile_kb(user.language))
    await safe_answer(call)


@router.message(Command("blocklist"))
async def blocklist_cmd(message: Message, session: AsyncSession) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    block_repo = BlockRepository(session)
    blocked_ids = await block_repo.list_for_user(user.id)
    if not blocked_ids:
        await message.answer("Блоклист пуст.")
        return
    repo = UserRepository(session)
    lines = []
    kb = InlineKeyboardBuilder()
    for bid in blocked_ids:
        u = await repo.get(bid)
        nick = u.roblox_nick if u else str(bid)
        lines.append(f"- {nick}")
        kb.button(text=f"Разблокировать {nick}", callback_data=f"unblock:{bid}")
    kb.adjust(1)
    await message.answer("Заблокированные:\n" + "\n".join(lines), reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("unblock:"))
async def unblock_cb(call: CallbackQuery, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    target_id = int(call.data.split(":")[1])
    await BlockRepository(session).remove(user.id, target_id)
    await session.commit()
    await call.message.answer("Разблокировано.")
    await safe_answer(call)


@router.callback_query(F.data.startswith("profile_edit:"))
async def profile_edit_cb(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    field = call.data.split(":")[1]
    lang = user.language

    if field == "nick":
        await state.set_state(ProfileEditStates.nick)
        await call.message.answer(t(lang, "ask_nick"))
    elif field == "age":
        await state.set_state(ProfileEditStates.age)
        await call.message.answer(t(lang, "ask_age"))
    elif field == "lang":
        await state.set_state(ProfileEditStates.language)
        await call.message.answer(t(lang, "ask_lang"), reply_markup=language_kb("edit_lang", lang, selected=lang))
    elif field == "modes":
        await state.set_state(ProfileEditStates.modes)
        await state.update_data(modes=list(user.modes))
        await call.message.answer(t(lang, "ask_modes"), reply_markup=modes_kb("edit_mode", lang, list(user.modes)))
    elif field == "bio":
        await state.set_state(ProfileEditStates.bio)
        await call.message.answer(t(lang, "ask_bio"))
    elif field == "avatar":
        await state.set_state(ProfileEditStates.avatar)
        await call.message.answer(t(lang, "ask_avatar"), reply_markup=skip_kb("edit_avatar:skip", lang))
    await safe_answer(call)


@router.callback_query(F.data == "profile_delete")
async def profile_delete_cb(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    lang = user.language
    await state.set_state(ProfileEditStates.delete_confirm)
    await call.message.answer(
        "Удалить профиль? Это действие необратимо.",
        reply_markup=confirm_kb("profile_delete_yes", "profile_delete_no", lang),
    )
    await safe_answer(call)


@router.callback_query(ProfileEditStates.delete_confirm, F.data.in_({"profile_delete_yes", "profile_delete_no"}))
async def profile_delete_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    if call.data == "profile_delete_yes":
        await UserRepository(session).delete(user.id)
        await session.commit()
        await state.clear()
        await call.message.answer("Профиль удалён. /start чтобы зарегистрироваться заново.")
    else:
        await state.clear()
        await call.message.answer("Отменено.")
    await safe_answer(call)


@router.message(ProfileEditStates.nick)
async def edit_nick(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    nick = (message.text or "").strip()
    if not NICK_RE.match(nick):
        await message.answer("Ник должен быть 3–20 символов.")
        return
    repo = UserRepository(session)
    if await repo.is_nick_taken(nick):
        await message.answer(t(user.language, "nick_taken"))
        return
    await repo.update_fields(user.id, roblox_nick=nick)
    await session.commit()
    await state.clear()
    await message.answer("Ник обновлён.", reply_markup=profile_kb(user.language))


@router.message(ProfileEditStates.age)
async def edit_age(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    try:
        age = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите число.")
        return
    if not 8 <= age <= 99:
        await message.answer("Возраст 8–99.")
        return
    await UserRepository(session).update_fields(user.id, age=age)
    await session.commit()
    await state.clear()
    await message.answer("Возраст обновлён.", reply_markup=profile_kb(user.language))


@router.callback_query(ProfileEditStates.language, F.data.startswith("edit_lang:"))
async def edit_lang(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    code = call.data.split(":")[1]
    await UserRepository(session).update_fields(user.id, language=code)
    await session.commit()
    await state.clear()
    await call.message.answer("Язык обновлён.", reply_markup=profile_kb(code))
    await safe_answer(call)


@router.callback_query(ProfileEditStates.modes, F.data.startswith("edit_mode:"))
async def edit_modes(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    data = await state.get_data()
    selected: list[str] = data.get("modes", [])
    code = call.data.split(":")[1]
    lang = user.language

    if code == "done":
        if not selected:
            await safe_answer(call, "Выбери хотя бы один режим.")
            return
        await UserRepository(session).update_fields(user.id, modes=selected)
        await session.commit()
        await state.clear()
        await call.message.answer("Режимы обновлены.", reply_markup=profile_kb(lang))
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
    await safe_edit_reply_markup(call.message, reply_markup=modes_kb("edit_mode", lang, selected))
    await safe_answer(call)


@router.message(ProfileEditStates.bio)
async def edit_bio(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    bio = (message.text or "").strip()
    if len(bio) > 200:
        bio = bio[:200]
    await UserRepository(session).update_fields(user.id, bio=bio)
    await session.commit()
    await state.clear()
    await message.answer("Описание обновлено.", reply_markup=profile_kb(user.language))


@router.callback_query(ProfileEditStates.avatar, F.data == "edit_avatar:skip")
async def edit_avatar_skip(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_call(call, session)
    if not user:
        return
    await UserRepository(session).update_fields(user.id, avatar_file_id=None)
    await session.commit()
    await state.clear()
    await call.message.answer("Аватар удалён.", reply_markup=profile_kb(user.language))
    await safe_answer(call)


@router.message(ProfileEditStates.avatar, F.photo)
async def edit_avatar_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await ensure_registered_message(message, session)
    if not user:
        return
    file_id = message.photo[-1].file_id
    await UserRepository(session).update_fields(user.id, avatar_file_id=file_id)
    await session.commit()
    await state.clear()
    await message.answer("Аватар обновлён.", reply_markup=profile_kb(user.language))
