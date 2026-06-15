from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

try:
    from .config import Config, load_config
    from .keyboards import SETUP_INSTRUCTIONS_CALLBACK, start_keyboard
    from .rules import check_message, normalize_text
    from .storage import AdabStorage
except ImportError:
    from config import Config, load_config
    from keyboards import SETUP_INSTRUCTIONS_CALLBACK, start_keyboard
    from rules import check_message, normalize_text
    from storage import AdabStorage


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

GROUP_TYPES = {"group", "supergroup"}

HELP_TEXT = (
    "Я мягко напоминаю об адабе, когда вижу мат, угрозы, прямые оскорбления, "
    "грубый капс, флуд или повторы. Религиозные споры и термины сами по себе "
    "не оцениваю, ничего не удаляю, не баню и не мутю."
)

START_TEXT = """Ассаляму алейкум!

Я бот для напоминания об адабе общения в чате.
Я не удаляю сообщения, не баню и не решаю религиозные споры.
Я только мягко напоминаю сохранять уважительный тон, если в чате появляются мат, оскорбления, угрозы, флуд или грубость.

Чтобы я работал в группе:
1. Добавьте меня в чат.
2. Дайте мне право читать сообщения.
3. Отключите Privacy Mode через @BotFather."""

SETUP_INSTRUCTIONS_TEXT = """- Открой @BotFather
- Выбери своего бота
- Bot Settings
- Group Privacy
- Turn off
- Добавь бота в группу
- Проверь, что он видит сообщения"""


def register_handlers(
    dp: Dispatcher,
    storage: AdabStorage,
    config: Config,
) -> None:
    @dp.message(Command("start"))
    async def start(message: Message, bot: Bot) -> None:
        if _from_bot(message) or message.chat.type != "private":
            return

        bot_info = await bot.get_me()
        await _safe_reply(
            message,
            START_TEXT,
            reply_markup=start_keyboard(bot_info.username or ""),
        )

    @dp.callback_query(F.data == SETUP_INSTRUCTIONS_CALLBACK)
    async def setup_instructions(callback: CallbackQuery) -> None:
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer(SETUP_INSTRUCTIONS_TEXT, disable_notification=True)

    @dp.message(Command("adab_help"))
    async def adab_help(message: Message) -> None:
        if _from_bot(message):
            return
        await _safe_reply(message, HELP_TEXT)

    @dp.message(Command("adab_status"))
    async def adab_status(message: Message, bot: Bot) -> None:
        if _from_bot(message):
            return
        if message.chat.type not in GROUP_TYPES:
            await _safe_reply(message, "Команда доступна администраторам группы.")
            return
        if message.from_user is None or not await _is_admin(bot, message.chat.id, message.from_user.id):
            await _safe_reply(message, "Команда доступна только администраторам группы.")
            return

        total_warnings = await storage.get_chat_warning_count(message.chat.id)
        await _safe_reply(
            message,
            f"Бот активен. Всего мягких предупреждений в этом чате: {total_warnings}.",
        )

    @dp.message(F.text)
    async def moderate_text(message: Message) -> None:
        if _from_bot(message) or message.from_user is None:
            return
        if message.chat.type not in GROUP_TYPES:
            return

        text = message.text or ""
        if not text or text.startswith("/"):
            return

        normalized = normalize_text(text)
        await storage.record_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            text=text,
            normalized_text=normalized,
        )
        history_window = max(config.flood_time_window_seconds, 60)
        history_limit = max(config.flood_messages_limit + 5, 10)
        recent_messages = await storage.get_recent_messages(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            window_seconds=history_window,
            limit=history_limit,
        )

        result = check_message(
            text,
            message.from_user.id,
            message.chat.id,
            recent_messages=recent_messages,
            settings=config,
        )
        if not result["violation"]:
            return

        cooldown = await storage.can_warn(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            user_cooldown_seconds=config.user_cooldown_seconds,
            chat_cooldown_seconds=config.chat_cooldown_seconds,
        )
        logger.debug(
            "Moderation cooldown: chat_id=%s user_id=%s category=%s allowed=%s reason=%s",
            message.chat.id,
            message.from_user.id,
            result["category"],
            cooldown.allowed,
            cooldown.reason,
        )
        if not cooldown.allowed:
            logger.debug("Skipped warning because of %s", cooldown.reason)
            return

        if await _safe_reply(message, str(result["reply"])):
            await storage.mark_warning(message.chat.id, message.from_user.id)


async def _is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except TelegramAPIError:
        logger.exception("Failed to check admin status")
        return False
    return member.status in {
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
        "administrator",
        "creator",
    }


async def _safe_reply(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        await message.reply(text, disable_notification=True, reply_markup=reply_markup)
        return True
    except TelegramAPIError:
        logger.exception("Failed to send Telegram reply")
        return False


def _from_bot(message: Message) -> bool:
    return message.from_user is not None and message.from_user.is_bot


async def _set_commands(bot: Bot) -> None:
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Приветствие и добавление в группу"),
                BotCommand(command="adab_help", description="Как работает бот адаба"),
                BotCommand(command="adab_status", description="Статус и предупреждения"),
            ]
        )
    except TelegramAPIError:
        logger.exception("Failed to set bot commands")


def _build_runtime(config: Config) -> tuple[AdabStorage, Bot, Dispatcher]:
    storage = AdabStorage(config.database_path)

    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    register_handlers(dp, storage, config)
    return storage, bot, dp


async def _run_polling(config: Config) -> None:
    storage, bot, dp = _build_runtime(config)
    await storage.connect()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await _set_commands(bot)
        logger.info("Adab bot started in polling mode")
        await dp.start_polling(bot)
    finally:
        await storage.close()
        await bot.session.close()


async def _run_webhook(config: Config) -> None:
    storage, bot, dp = _build_runtime(config)
    webhook_url = f"{config.webhook_base_url}{config.webhook_path}"

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="Adab bot is running")

    async def on_startup(_: web.Application) -> None:
        await storage.connect()
        await _set_commands(bot)
        await bot.set_webhook(
            webhook_url,
            secret_token=config.webhook_secret_token or None,
            drop_pending_updates=True,
        )
        logger.info("Adab bot started in webhook mode: %s", webhook_url)

    async def on_cleanup(_: web.Application) -> None:
        await storage.close()

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config.webhook_secret_token or None,
        handle_in_background=True,
    ).register(app, path=config.webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=config.web_host, port=config.web_port)
    try:
        await site.start()
        logger.info("HTTP server listening on %s:%s", config.web_host, config.web_port)
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config()
    if config.webhook_base_url:
        await _run_webhook(config)
    else:
        await _run_polling(config)


if __name__ == "__main__":
    asyncio.run(main())
