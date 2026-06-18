from __future__ import annotations

import asyncio
import logging
from time import time

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    CallbackQuery,
    InlineKeyboardMarkup,
    LabeledPrice,
    MenuButtonCommands,
    Message,
    PreCheckoutQuery,
    ReplyKeyboardMarkup,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

try:
    from .config import Config, load_config
    from .keyboards import (
        BUG_BUTTON_TEXT,
        HELP_BUTTON_TEXT,
        SUPPORT_AMOUNTS,
        SUPPORT_BUTTON_TEXT,
        private_main_keyboard,
        start_keyboard,
        support_amounts_keyboard,
    )
    from .rules import check_message, normalize_text
    from .storage import AdabStorage
except ImportError:
    from config import Config, load_config
    from keyboards import (
        BUG_BUTTON_TEXT,
        HELP_BUTTON_TEXT,
        SUPPORT_AMOUNTS,
        SUPPORT_BUTTON_TEXT,
        private_main_keyboard,
        start_keyboard,
        support_amounts_keyboard,
    )
    from rules import check_message, normalize_text
    from storage import AdabStorage


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

GROUP_TYPES = {"group", "supergroup"}

TASLIM_TEXT = "السلام عليكم ورحمة الله وبركاته"

START_TEXT = f"""{TASLIM_TEXT}

Я бот для напоминания об адабе общения в чате.

Я помогаю сохранять адаб общения в чате.
Если разговор становится грубым, появляются оскорбления, угрозы, флуд или резкий тон — я мягко напоминаю участникам говорить спокойно и с уважением.

Чтобы я работал в группе:
1. Добавьте меня в чат.
2. Дайте мне право читать сообщения.

Если нашли баг или хотите предложить улучшение - напишите: @AbuSidq"""

HELP_TEXT = f"""{TASLIM_TEXT}

Я помогаю сохранять адаб общения в чате.

Что я отслеживаю:
• мат и грубую речь;
• личные оскорбления;
• угрозы;
• флуд и повторы;
• агрессивный капс;
• грубые провокации.

Что я НЕ делаю:
• не удаляю сообщения;
• не баню и не мутю;
• не решаю религиозные споры;
• не оцениваю, кто прав.

Я только мягко напоминаю участникам сохранять уважительный тон.

Если нашли баг или ложное срабатывание — напишите: @AbuSidq"""

SUPPORT_TEXT = f"""{TASLIM_TEXT}

Вы можете поддержать развитие бота через Telegram Stars.

Поддержка помогает развивать проект, исправлять ошибки и улучшать напоминания об адабе.

Выберите сумму:"""

BUG_REPORT_TEXT = f"""{TASLIM_TEXT}

Если вы нашли баг, заметили ложное срабатывание или хотите предложить улучшение — напишите:

@AbuSidq

Желательно указать:
• что написал пользователь;
• как ответил бот;
• почему, по вашему мнению, это ошибка."""

SUPPORT_THANKS_TEXT = """Спасибо вам большое за поддержку проекта!

Ваш вклад помогает развивать бота, исправлять ошибки и делать напоминания об адабе лучше и полезнее.
Очень ценю вашу поддержку, доверие и желание помочь этому делу.
Пусть Аллах примет это от вас, увеличит вам благо, даст баракат в делах и воздаст вам намного большим.

جزاك اللهُ خيرًا"""


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

    @dp.message(Command("help"))
    @dp.message(Command("adab_help"))
    async def adab_help(message: Message) -> None:
        if _from_bot(message):
            return
        await _safe_reply(
            message,
            HELP_TEXT,
            reply_markup=private_main_keyboard() if is_private_chat(message) else None,
        )

    @dp.message(Command("support"))
    @dp.message(F.text == SUPPORT_BUTTON_TEXT)
    async def support(message: Message) -> None:
        if _from_bot(message):
            return
        if message.chat.type != "private":
            await _safe_reply(message, "Поддержать проект можно в личном чате с ботом: /support")
            return
        await _send_support_options(message)

    @dp.message(Command("bug"))
    @dp.message(F.text == BUG_BUTTON_TEXT)
    async def report_bug(message: Message) -> None:
        if _from_bot(message):
            return
        await _safe_reply(
            message,
            BUG_REPORT_TEXT,
            reply_markup=private_main_keyboard() if is_private_chat(message) else None,
        )

    @dp.message(F.text == HELP_BUTTON_TEXT)
    async def help_button(message: Message) -> None:
        if _from_bot(message):
            return
        await _safe_reply(
            message,
            HELP_TEXT,
            reply_markup=private_main_keyboard() if is_private_chat(message) else None,
        )

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

    @dp.message(F.text | F.caption)
    async def moderate_text(message: Message) -> None:
        if _from_bot(message) or message.from_user is None:
            return
        if message.chat.type not in GROUP_TYPES:
            return

        text = message.text or message.caption or ""
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

    @dp.callback_query(F.data.startswith("support_stars:"))
    async def support_stars_callback(callback: CallbackQuery) -> None:
        print("[SUPPORT_CALLBACK]", callback.data, callback.from_user.id, flush=True)
        if callback.from_user.is_bot:
            return

        amount = _support_amount_from_callback(callback.data or "")
        if amount is None:
            await callback.answer("Неверная сумма.", show_alert=True)
            return

        await callback.answer()

        message = callback.message
        if not isinstance(message, Message):
            logger.warning("Cannot send Stars invoice because callback message is unavailable")
            return

        payload = f"support_stars:{callback.from_user.id}:{amount}:{int(time())}"
        print("[SUPPORT_INVOICE]", amount, callback.from_user.id, flush=True)
        try:
            await message.answer_invoice(
                title=f"Поддержка Adab Protector — {amount} ⭐",
                description=f"Добровольная поддержка проекта на {amount} Telegram Stars. Спасибо за помощь в развитии бота.",
                payload=payload,
                currency="XTR",
                prices=[LabeledPrice(label=f"Поддержка проекта — {amount} ⭐", amount=amount)],
                provider_token="",
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                is_flexible=False,
                disable_notification=True,
            )
        except TelegramAPIError:
            logger.exception("Failed to send Stars invoice")

    @dp.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery) -> None:
        payload = query.invoice_payload or ""
        if payload.startswith("support_stars:"):
            await query.answer(ok=True)
            return
        await query.answer(ok=False, error_message="Неизвестный платёж.")

    @dp.message(F.successful_payment)
    async def successful_payment(message: Message) -> None:
        payment = message.successful_payment
        if payment is None:
            return

        payload = payment.invoice_payload or ""
        if payment.currency == "XTR" and payload.startswith("support_stars:"):
            await _safe_reply(
                message,
                SUPPORT_THANKS_TEXT,
                reply_markup=private_main_keyboard() if is_private_chat(message) else None,
            )
            if message.from_user is None:
                return
            try:
                await storage.add_support_payment(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    full_name=message.from_user.full_name,
                    amount=payment.total_amount,
                    currency=payment.currency,
                    payload=payload,
                    telegram_payment_charge_id=payment.telegram_payment_charge_id,
                    provider_payment_charge_id=payment.provider_payment_charge_id,
                )
            except Exception:
                logger.exception("Failed to record support payment")


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
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None,
) -> bool:
    try:
        await message.reply(text, disable_notification=True, reply_markup=reply_markup)
        return True
    except TelegramAPIError:
        logger.exception("Failed to send Telegram reply")
        return False


async def _send_support_options(message: Message) -> None:
    await _safe_reply(message, SUPPORT_TEXT, reply_markup=support_amounts_keyboard())


def _support_amount_from_callback(data: str) -> int | None:
    prefix = "support_stars:"
    if not data.startswith(prefix):
        return None
    try:
        amount = int(data.removeprefix(prefix))
    except ValueError:
        return None
    if amount not in SUPPORT_AMOUNTS:
        return None
    return amount


def _from_bot(message: Message) -> bool:
    return message.from_user is not None and message.from_user.is_bot


def is_private_chat(message: Message) -> bool:
    return message.chat.type == "private"


async def _set_commands(bot: Bot) -> None:
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Запустить бота"),
                BotCommand(command="help", description="ℹ️ Помощь"),
                BotCommand(command="support", description="❤️ Поддержать проект"),
                BotCommand(command="bug", description="🛠 Сообщить о баге"),
            ],
            scope=BotCommandScopeAllPrivateChats(),
        )
        await bot.set_my_commands(
            [
                BotCommand(command="adab_status", description="Статус и предупреждения"),
            ],
            scope=BotCommandScopeDefault(),
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
        return web.json_response({"status": "ok"})

    async def on_startup(_: web.Application) -> None:
        await storage.connect()
        await _set_commands(bot)
        await bot.set_webhook(
            webhook_url,
            secret_token=config.webhook_secret_token or None,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types(),
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
