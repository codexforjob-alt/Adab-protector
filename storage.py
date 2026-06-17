from __future__ import annotations

from datetime import datetime, timezone
import time
from dataclasses import dataclass
from typing import Any

import aiosqlite


@dataclass(frozen=True)
class CooldownResult:
    allowed: bool
    reason: str = ""


class AdabStorage:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        self.db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.db = await aiosqlite.connect(self.database_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")
        await self._create_schema()

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None

    async def _create_schema(self) -> None:
        db = self._db()
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_warnings (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                last_warning_time INTEGER NOT NULL DEFAULT 0,
                warning_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS chat_state (
                chat_id INTEGER PRIMARY KEY,
                last_global_warning_time INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_history_chat_user_time
            ON message_history (chat_id, user_id, created_at);

            CREATE TABLE IF NOT EXISTS support_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                amount INTEGER,
                currency TEXT,
                payload TEXT,
                telegram_payment_charge_id TEXT,
                provider_payment_charge_id TEXT,
                created_at TEXT
            );
            """
        )
        await db.commit()

    async def init_support_payments_table(self) -> None:
        db = self._db()
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS support_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                amount INTEGER,
                currency TEXT,
                payload TEXT,
                telegram_payment_charge_id TEXT,
                provider_payment_charge_id TEXT,
                created_at TEXT
            )
            """
        )
        await db.commit()

    async def add_support_payment(
        self,
        user_id: int,
        username: str | None,
        full_name: str | None,
        amount: int,
        currency: str,
        payload: str,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str,
        created_at: str | None = None,
    ) -> None:
        db = self._db()
        await db.execute(
            """
            INSERT INTO support_payments (
                user_id,
                username,
                full_name,
                amount,
                currency,
                payload,
                telegram_payment_charge_id,
                provider_payment_charge_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                full_name,
                amount,
                currency,
                payload,
                telegram_payment_charge_id,
                provider_payment_charge_id,
                created_at or datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()

    async def record_message(
        self,
        chat_id: int,
        user_id: int,
        text: str,
        normalized_text: str,
        created_at: int | None = None,
    ) -> None:
        now = created_at or int(time.time())
        db = self._db()
        await db.execute(
            """
            INSERT INTO message_history (chat_id, user_id, message_text, normalized_text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, user_id, text, normalized_text, now),
        )
        # The bot only needs fresh context. Keeping one day is enough for spam checks.
        await db.execute(
            "DELETE FROM message_history WHERE created_at < ?",
            (now - 86400,),
        )
        await db.commit()

    async def get_recent_messages(
        self,
        chat_id: int,
        user_id: int,
        window_seconds: int,
        limit: int = 20,
        now: int | None = None,
    ) -> list[dict[str, Any]]:
        current_time = now or int(time.time())
        db = self._db()
        cursor = await db.execute(
            """
            SELECT message_text, normalized_text, created_at
            FROM message_history
            WHERE chat_id = ? AND user_id = ? AND created_at >= ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (chat_id, user_id, current_time - window_seconds, limit),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(row) for row in reversed(rows)]

    async def can_warn(
        self,
        chat_id: int,
        user_id: int,
        user_cooldown_seconds: int,
        chat_cooldown_seconds: int,
        now: int | None = None,
    ) -> CooldownResult:
        current_time = now or int(time.time())
        db = self._db()

        cursor = await db.execute(
            """
            SELECT last_warning_time
            FROM user_warnings
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        )
        user_row = await cursor.fetchone()
        await cursor.close()
        if user_row and current_time - int(user_row["last_warning_time"]) < user_cooldown_seconds:
            return CooldownResult(False, "user_cooldown")

        cursor = await db.execute(
            """
            SELECT last_global_warning_time
            FROM chat_state
            WHERE chat_id = ?
            """,
            (chat_id,),
        )
        chat_row = await cursor.fetchone()
        await cursor.close()
        if chat_row and current_time - int(chat_row["last_global_warning_time"]) < chat_cooldown_seconds:
            return CooldownResult(False, "chat_cooldown")

        return CooldownResult(True)

    async def mark_warning(self, chat_id: int, user_id: int, now: int | None = None) -> None:
        current_time = now or int(time.time())
        db = self._db()
        await db.execute(
            """
            INSERT INTO user_warnings (chat_id, user_id, last_warning_time, warning_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                last_warning_time = excluded.last_warning_time,
                warning_count = user_warnings.warning_count + 1
            """,
            (chat_id, user_id, current_time),
        )
        await db.execute(
            """
            INSERT INTO chat_state (chat_id, last_global_warning_time)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                last_global_warning_time = excluded.last_global_warning_time
            """,
            (chat_id, current_time),
        )
        await db.commit()

    async def get_user_warning_count(self, chat_id: int, user_id: int) -> int:
        db = self._db()
        cursor = await db.execute(
            """
            SELECT warning_count
            FROM user_warnings
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return 0
        return int(row["warning_count"])

    async def get_chat_warning_count(self, chat_id: int) -> int:
        db = self._db()
        cursor = await db.execute(
            """
            SELECT COALESCE(SUM(warning_count), 0) AS total
            FROM user_warnings
            WHERE chat_id = ?
            """,
            (chat_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return int(row["total"] if row else 0)

    def _db(self) -> aiosqlite.Connection:
        if self.db is None:
            raise RuntimeError("Storage is not connected")
        return self.db
