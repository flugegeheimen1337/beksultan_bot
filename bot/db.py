from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from bot.timeutils import to_utc_iso

INCOME = "income"
EXPENSE = "expense"
CASH = "cash"
CARD = "card"
_UNSET = object()
DIRECTION_IN = "in"
DIRECTION_OUT = "out"
STATUS_OPEN = "open"
STATUS_CLOSED = "closed"


@dataclass(frozen=True)
class Operation:
    id: int
    chat_id: int
    user_id: int | None
    user_name: str
    kind: str
    amount_kop: int
    comment: str
    created_at: str
    pocket: str | None = None


@dataclass(frozen=True)
class Debt:
    id: int
    chat_id: int
    user_id: int | None
    user_name: str
    person: str
    direction: str
    amount_kop: int
    paid_kop: int
    comment: str
    status: str
    created_at: str
    closed_at: str | None

    @property
    def rest_kop(self) -> int:
        return max(self.amount_kop - self.paid_kop, 0)


@dataclass(frozen=True)
class Payment:
    id: int
    debt_id: int
    chat_id: int
    person: str
    amount_kop: int
    created_at: str


@dataclass(frozen=True)
class PayResult:
    ok: bool
    reason: str
    debt: Debt | None = None


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _init(self) -> None:
        with self._lock:
            connection = self._connect()
            try:
                connection.executescript(
                    """
                    PRAGMA journal_mode=WAL;
                    CREATE TABLE IF NOT EXISTS operations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER NOT NULL,
                        user_id INTEGER,
                        user_name TEXT NOT NULL DEFAULT '',
                        kind TEXT NOT NULL CHECK(kind IN ('income', 'expense')),
                        amount_kop INTEGER NOT NULL CHECK(amount_kop > 0),
                        comment TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        pocket TEXT CHECK(pocket IN ('cash', 'card'))
                    );
                    CREATE INDEX IF NOT EXISTS idx_ops_chat_time
                        ON operations(chat_id, created_at);

                    CREATE TABLE IF NOT EXISTS debts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER NOT NULL,
                        user_id INTEGER,
                        user_name TEXT NOT NULL DEFAULT '',
                        person TEXT NOT NULL,
                        direction TEXT NOT NULL CHECK(direction IN ('in', 'out')),
                        amount_kop INTEGER NOT NULL CHECK(amount_kop > 0),
                        paid_kop INTEGER NOT NULL DEFAULT 0 CHECK(paid_kop >= 0),
                        comment TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
                        created_at TEXT NOT NULL,
                        closed_at TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_debts_chat
                        ON debts(chat_id, status);

                    CREATE TABLE IF NOT EXISTS payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        debt_id INTEGER NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
                        chat_id INTEGER NOT NULL,
                        amount_kop INTEGER NOT NULL CHECK(amount_kop > 0),
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_payments_chat
                        ON payments(chat_id, created_at);

                    CREATE TABLE IF NOT EXISTS settings (
                        chat_id INTEGER PRIMARY KEY,
                        auto_report INTEGER NOT NULL DEFAULT 0,
                        last_auto_date TEXT
                    );
                    """
                )
                columns = {row[1] for row in connection.execute("PRAGMA table_info(operations)")}
                if "pocket" not in columns:
                    connection.execute("ALTER TABLE operations ADD COLUMN pocket TEXT")
                connection.commit()
            finally:
                connection.close()

    def add_operation(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        user_name: str,
        kind: str,
        amount_kop: int,
        comment: str,
        created_at: str | None = None,
        pocket: str | None = None,
    ) -> Operation:
        moment = created_at or to_utc_iso()

        def write(connection: sqlite3.Connection) -> Operation:
            cursor = connection.execute(
                """
                INSERT INTO operations (
                    chat_id, user_id, user_name, kind, amount_kop, comment, created_at, pocket
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, user_name, kind, amount_kop, comment, moment, pocket),
            )
            return self._operation(
                connection.execute(
                    "SELECT * FROM operations WHERE id=?",
                    (cursor.lastrowid,),
                ).fetchone()
            )

        return self._write(write)

    def operations_between(
        self,
        chat_id: int,
        start_iso: str | None,
        end_iso: str | None,
    ) -> list[Operation]:
        sql = "SELECT * FROM operations WHERE chat_id=?"
        args: list[object] = [chat_id]
        if start_iso is not None:
            sql += " AND created_at>=?"
            args.append(start_iso)
        if end_iso is not None:
            sql += " AND created_at<?"
            args.append(end_iso)
        sql += " ORDER BY created_at, id"
        return [self._operation(row) for row in self._read(sql, args)]

    def get_operation(self, chat_id: int, operation_id: int) -> Operation | None:
        rows = self._read(
            "SELECT * FROM operations WHERE chat_id=? AND id=?",
            [chat_id, operation_id],
        )
        if not rows:
            return None
        return self._operation(rows[0])

    def recent_operations(self, chat_id: int, limit: int = 20) -> list[Operation]:
        rows = self._read(
            """
            SELECT * FROM operations
            WHERE chat_id=?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            [chat_id, limit],
        )
        return [self._operation(row) for row in rows]

    def update_operation(
        self,
        chat_id: int,
        operation_id: int,
        *,
        kind: str | None = None,
        amount_kop: int | None = None,
        comment: str | None = None,
        pocket: str | None | object = _UNSET,
    ) -> Operation | None:
        def write(connection: sqlite3.Connection) -> Operation | None:
            row = connection.execute(
                "SELECT * FROM operations WHERE chat_id=? AND id=?",
                (chat_id, operation_id),
            ).fetchone()
            if row is None:
                return None
            current = self._operation(row)
            connection.execute(
                """
                UPDATE operations
                SET kind=?, amount_kop=?, comment=?, pocket=?
                WHERE chat_id=? AND id=?
                """,
                (
                    current.kind if kind is None else kind,
                    current.amount_kop if amount_kop is None else amount_kop,
                    current.comment if comment is None else comment,
                    current.pocket if pocket is _UNSET else pocket,
                    chat_id,
                    operation_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM operations WHERE id=?",
                (operation_id,),
            ).fetchone()
            return self._operation(updated)

        return self._write(write)

    def delete_operation(self, chat_id: int, operation_id: int) -> bool:
        def write(connection: sqlite3.Connection) -> bool:
            cursor = connection.execute(
                "DELETE FROM operations WHERE chat_id=? AND id=?",
                (chat_id, operation_id),
            )
            return cursor.rowcount > 0

        return self._write(write)

    def add_debt(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        user_name: str,
        person: str,
        direction: str,
        amount_kop: int,
        comment: str,
        created_at: str | None = None,
    ) -> Debt:
        moment = created_at or to_utc_iso()

        def write(connection: sqlite3.Connection) -> Debt:
            cursor = connection.execute(
                """
                INSERT INTO debts (
                    chat_id, user_id, user_name, person, direction,
                    amount_kop, paid_kop, comment, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, 'open', ?)
                """,
                (chat_id, user_id, user_name, person, direction, amount_kop, comment, moment),
            )
            return self._debt(
                connection.execute("SELECT * FROM debts WHERE id=?", (cursor.lastrowid,)).fetchone()
            )

        return self._write(write)

    def list_debts(self, chat_id: int, status: str | None = None) -> list[Debt]:
        sql = "SELECT * FROM debts WHERE chat_id=?"
        args: list[object] = [chat_id]
        if status is not None:
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, created_at, id"
        return [self._debt(row) for row in self._read(sql, args)]

    def get_debt(self, chat_id: int, debt_id: int) -> Debt | None:
        rows = self._read(
            "SELECT * FROM debts WHERE chat_id=? AND id=?",
            [chat_id, debt_id],
        )
        if not rows:
            return None
        return self._debt(rows[0])

    def add_payment(self, chat_id: int, debt_id: int, amount_kop: int) -> PayResult:
        def write(connection: sqlite3.Connection) -> PayResult:
            row = connection.execute(
                "SELECT * FROM debts WHERE chat_id=? AND id=?",
                (chat_id, debt_id),
            ).fetchone()
            if row is None:
                return PayResult(False, "missing")
            debt = self._debt(row)
            if debt.status != STATUS_OPEN:
                return PayResult(False, "closed", debt)
            if amount_kop <= 0 or amount_kop > debt.rest_kop:
                return PayResult(False, "too_much", debt)
            moment = to_utc_iso()
            connection.execute(
                """
                INSERT INTO payments (debt_id, chat_id, amount_kop, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (debt_id, chat_id, amount_kop, moment),
            )
            paid = debt.paid_kop + amount_kop
            closed = paid >= debt.amount_kop
            connection.execute(
                """
                UPDATE debts
                SET paid_kop=?, status=?, closed_at=?
                WHERE id=?
                """,
                (paid, STATUS_CLOSED if closed else STATUS_OPEN, moment if closed else None, debt_id),
            )
            updated = self._debt(
                connection.execute("SELECT * FROM debts WHERE id=?", (debt_id,)).fetchone()
            )
            return PayResult(True, "ok", updated)

        return self._write(write)

    def delete_debt(self, chat_id: int, debt_id: int) -> bool:
        def write(connection: sqlite3.Connection) -> bool:
            cursor = connection.execute(
                "DELETE FROM debts WHERE chat_id=? AND id=?",
                (chat_id, debt_id),
            )
            return cursor.rowcount > 0

        return self._write(write)

    def list_payments(self, chat_id: int) -> list[Payment]:
        rows = self._read(
            """
            SELECT p.id, p.debt_id, p.chat_id, p.amount_kop, p.created_at, d.person
            FROM payments p
            JOIN debts d ON d.id = p.debt_id
            WHERE p.chat_id=?
            ORDER BY p.created_at, p.id
            """,
            [chat_id],
        )
        return [
            Payment(
                id=row["id"],
                debt_id=row["debt_id"],
                chat_id=row["chat_id"],
                person=row["person"],
                amount_kop=row["amount_kop"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def auto_enabled(self, chat_id: int) -> bool:
        rows = self._read("SELECT auto_report FROM settings WHERE chat_id=?", [chat_id])
        if not rows:
            return False
        return bool(rows[0]["auto_report"])

    def set_auto(self, chat_id: int, enabled: bool) -> None:
        def write(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO settings (chat_id, auto_report, last_auto_date)
                VALUES (?, ?, NULL)
                ON CONFLICT(chat_id) DO UPDATE SET auto_report=excluded.auto_report
                """,
                (chat_id, 1 if enabled else 0),
            )

        self._write(write)

    def mark_auto_sent(self, chat_id: int, day: str) -> None:
        def write(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO settings (chat_id, auto_report, last_auto_date)
                VALUES (?, 1, ?)
                ON CONFLICT(chat_id) DO UPDATE SET last_auto_date=excluded.last_auto_date
                """,
                (chat_id, day),
            )

        self._write(write)

    def auto_chats(self) -> list[tuple[int, str | None]]:
        rows = self._read(
            "SELECT chat_id, last_auto_date FROM settings WHERE auto_report=1",
            [],
        )
        return [(row["chat_id"], row["last_auto_date"]) for row in rows]

    def _write(self, fn):
        with self._lock:
            connection = self._connect()
            try:
                result = fn(connection)
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _read(self, sql: str, args: list[object]) -> list[sqlite3.Row]:
        with self._lock:
            connection = self._connect()
            try:
                return list(connection.execute(sql, args))
            finally:
                connection.close()

    @staticmethod
    def _operation(row: sqlite3.Row) -> Operation:
        return Operation(
            id=row["id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            kind=row["kind"],
            amount_kop=row["amount_kop"],
            comment=row["comment"],
            created_at=row["created_at"],
            pocket=row["pocket"],
        )

    @staticmethod
    def _debt(row: sqlite3.Row) -> Debt:
        return Debt(
            id=row["id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            person=row["person"],
            direction=row["direction"],
            amount_kop=row["amount_kop"],
            paid_kop=row["paid_kop"],
            comment=row["comment"],
            status=row["status"],
            created_at=row["created_at"],
            closed_at=row["closed_at"],
        )
