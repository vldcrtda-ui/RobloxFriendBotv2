from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter
from aiogram.types import CallbackQuery, Message


async def safe_answer(call: CallbackQuery, *args, **kwargs) -> None:
    try:
        await call.answer(*args, **kwargs)
    except (TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter):
        return
    except Exception:
        return


async def safe_edit_text(message: Message, *args, **kwargs) -> None:
    try:
        await message.edit_text(*args, **kwargs)
    except TelegramBadRequest:
        # Fallback: message might be too old to edit, send a new one instead
        try:
            text = args[0] if args else kwargs.get("text")
            reply_markup = kwargs.get("reply_markup")
            if text:
                await message.answer(text, reply_markup=reply_markup)
        except Exception:
            return
    except (TelegramNetworkError, TelegramRetryAfter):
        return
    except Exception:
        return


async def safe_edit_reply_markup(message: Message, *args, **kwargs) -> None:
    try:
        await message.edit_reply_markup(*args, **kwargs)
    except TelegramBadRequest:
        # Fallback: send a fresh keyboard if edit is not possible
        try:
            reply_markup = kwargs.get("reply_markup")
            if reply_markup:
                await message.answer("Обновлённое меню:", reply_markup=reply_markup)
        except Exception:
            return
    except (TelegramNetworkError, TelegramRetryAfter):
        return
    except Exception:
        return
