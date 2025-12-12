from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    nick = State()
    age = State()
    language = State()
    modes = State()
    bio = State()
    avatar = State()


class SearchStates(StatesGroup):
    language = State()
    age_range = State()
    modes = State()
    confirm = State()


class ProfileEditStates(StatesGroup):
    nick = State()
    age = State()
    language = State()
    modes = State()
    bio = State()
    avatar = State()
    delete_confirm = State()


class RandomChatStates(StatesGroup):
    confirm = State()


class BrowseFilterStates(StatesGroup):
    age_range = State()


class BroadcastStates(StatesGroup):
    text = State()
    confirm = State()


class AdminPanelStates(StatesGroup):
    user_search = State()
    user_ban_days = State()
    user_ban_reason = State()
    user_delete_confirm = State()
    games_add_code = State()
    games_add_names = State()
    games_remove_code = State()
