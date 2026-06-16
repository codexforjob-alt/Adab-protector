from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


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
        ]
    )
