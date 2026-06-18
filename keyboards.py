from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


SUPPORT_BUTTON_TEXT = "⭐ Поддержать проект"
BUG_BUTTON_TEXT = "🛠 Сообщить о баге"
HELP_BUTTON_TEXT = "ℹ️ Помощь"

SUPPORT_AMOUNTS = (10, 25, 50, 100)


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


def private_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SUPPORT_BUTTON_TEXT)],
            [
                KeyboardButton(text=BUG_BUTTON_TEXT),
                KeyboardButton(text=HELP_BUTTON_TEXT),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def private_menu_keyboard() -> ReplyKeyboardMarkup:
    return private_main_keyboard()


def support_amounts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ 10", callback_data="support_stars:10"),
                InlineKeyboardButton(text="⭐ 25", callback_data="support_stars:25"),
            ],
            [
                InlineKeyboardButton(text="⭐ 50", callback_data="support_stars:50"),
                InlineKeyboardButton(text="⭐ 100", callback_data="support_stars:100"),
            ],
        ]
    )
