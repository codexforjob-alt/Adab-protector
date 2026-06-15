from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


SETUP_INSTRUCTIONS_CALLBACK = "setup_instructions"


def start_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    username = bot_username.removeprefix("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Добавить бота в чат",
                    url=f"https://t.me/{username}?startgroup=true",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Как настроить",
                    callback_data=SETUP_INSTRUCTIONS_CALLBACK,
                )
            ],
        ]
    )
