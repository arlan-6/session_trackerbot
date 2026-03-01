from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils.time_utils import compute_week_bounds


@dataclass
class Session:
    id: int
    user_id: int
    start_time: datetime
    end_time: datetime | None
    duration_seconds: int | None
    created_at: datetime


class Database:
    DEFAULT_WEEK_TARGET_SECONDS = 30 * 3600

    def __init__(self, path: str) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _to_iso(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _from_iso(value: str | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value)

    @staticmethod
    def _row_to_session(row: sqlite3.Row | None) -> Session | None:
        if row is None:
            return None
        return Session(
            id=row["id"],
            user_id=row["user_id"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=Database._from_iso(row["end_time"]),
            duration_seconds=row["duration_seconds"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    timezone TEXT NOT NULL DEFAULT 'UTC',
                    week_start_day INTEGER NOT NULL DEFAULT 0,
                    target_week_seconds INTEGER NOT NULL DEFAULT 144000,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_users_columns(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS work_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_work_sessions_user_start
                ON work_sessions(user_id, start_time)
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_single_active_session
                ON work_sessions(user_id)
                WHERE end_time IS NULL
                """
            )

    @staticmethod
    def _has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(row["name"] == column_name for row in rows)

    def _ensure_users_columns(self, conn: sqlite3.Connection) -> None:
        if not self._has_column(conn, "users", "target_week_seconds"):
            conn.execute(
                f"""
                ALTER TABLE users
                ADD COLUMN target_week_seconds INTEGER NOT NULL
                DEFAULT {self.DEFAULT_WEEK_TARGET_SECONDS}
                """
            )

    def ensure_user(self, user_id: int) -> None:
        now = self._to_iso(datetime.now(timezone.utc))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, created_at)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id, now),
            )

    def get_user_settings(self, user_id: int) -> tuple[tzinfo, int]:
        self.ensure_user(user_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT timezone, week_start_day FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        timezone_name = row["timezone"] if row else "UTC"
        week_start_day = int(row["week_start_day"]) if row else 0
        try:
            tz = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            tz = timezone.utc
        return tz, week_start_day

    def get_user_timezone_name(self, user_id: int) -> str:
        self.ensure_user(user_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT timezone FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row["timezone"] if row else "UTC"

    def set_user_timezone(self, user_id: int, timezone_name: str) -> bool:
        self.ensure_user(user_id)
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return False
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET timezone = ?
                WHERE user_id = ?
                """,
                (timezone_name, user_id),
            )
        return True

    def get_week_target_seconds(self, user_id: int) -> int:
        self.ensure_user(user_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT target_week_seconds FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return self.DEFAULT_WEEK_TARGET_SECONDS
        return int(row["target_week_seconds"])

    def set_week_target_seconds(self, user_id: int, target_week_seconds: int) -> None:
        self.ensure_user(user_id)
        safe_target = max(0, int(target_week_seconds))
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET target_week_seconds = ?
                WHERE user_id = ?
                """,
                (safe_target, user_id),
            )

    def get_active_session(self, user_id: int) -> Session | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM work_sessions
                WHERE user_id = ? AND end_time IS NULL
                ORDER BY start_time DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return self._row_to_session(row)

    def start_session(self, user_id: int, started_at_utc: datetime) -> Session:
        self.ensure_user(user_id)
        active = self.get_active_session(user_id)
        if active:
            return active

        now_iso = self._to_iso(datetime.now(timezone.utc))
        start_iso = self._to_iso(started_at_utc)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO work_sessions (
                    user_id, start_time, end_time, duration_seconds, created_at
                )
                VALUES (?, ?, NULL, NULL, ?)
                """,
                (user_id, start_iso, now_iso),
            )
            session_id = int(cursor.lastrowid)
            row = conn.execute(
                "SELECT * FROM work_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        session = self._row_to_session(row)
        if not session:
            raise RuntimeError("Failed to create session")
        return session

    def end_latest_active_session(
        self, user_id: int, ended_at_utc: datetime
    ) -> Session | None:
        active = self.get_active_session(user_id)
        if not active:
            return None

        duration_seconds = int((ended_at_utc - active.start_time).total_seconds())
        duration_seconds = max(duration_seconds, 0)
        end_iso = self._to_iso(ended_at_utc)

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE work_sessions
                SET end_time = ?, duration_seconds = ?
                WHERE id = ?
                """,
                (end_iso, duration_seconds, active.id),
            )
            row = conn.execute(
                "SELECT * FROM work_sessions WHERE id = ?",
                (active.id,),
            ).fetchone()
        return self._row_to_session(row)

    def week_total_seconds(
        self, user_id: int, week_start_utc: datetime, week_end_utc: datetime
    ) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(duration_seconds), 0) AS total_seconds
                FROM work_sessions
                WHERE user_id = ?
                  AND duration_seconds IS NOT NULL
                  AND start_time >= ?
                  AND start_time < ?
                """,
                (user_id, self._to_iso(week_start_utc), self._to_iso(week_end_utc)),
            ).fetchone()
        return int(row["total_seconds"]) if row else 0

    def recent_sessions_for_week(
        self,
        user_id: int,
        week_start_utc: datetime,
        week_end_utc: datetime,
        limit: int = 5,
    ) -> list[Session]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM work_sessions
                WHERE user_id = ?
                  AND duration_seconds IS NOT NULL
                  AND start_time >= ?
                  AND start_time < ?
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (
                    user_id,
                    self._to_iso(week_start_utc),
                    self._to_iso(week_end_utc),
                    limit,
                ),
            ).fetchall()
        return [self._row_to_session(row) for row in rows if row is not None]

    def all_time_total_seconds(self, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(duration_seconds), 0) AS total_seconds
                FROM work_sessions
                WHERE user_id = ?
                  AND duration_seconds IS NOT NULL
                """,
                (user_id,),
            ).fetchone()
        return int(row["total_seconds"]) if row else 0

    def weekly_breakdown(
        self,
        user_id: int,
        tz: tzinfo,
        week_start_day: int,
        limit_weeks: int = 8,
    ) -> list[tuple[datetime, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT start_time, duration_seconds
                FROM work_sessions
                WHERE user_id = ?
                  AND duration_seconds IS NOT NULL
                ORDER BY start_time DESC
                """,
                (user_id,),
            ).fetchall()

        totals: defaultdict[datetime, int] = defaultdict(int)
        for row in rows:
            start_utc = datetime.fromisoformat(row["start_time"])
            duration = int(row["duration_seconds"])
            start_local = start_utc.astimezone(tz)
            week_start_local, _ = compute_week_bounds(
                start_local, tz=tz, week_start_day=week_start_day
            )
            totals[week_start_local] += duration

        ordered = sorted(totals.items(), key=lambda item: item[0], reverse=True)
        return ordered[:limit_weeks]

    def weekly_stats(self, user_id: int, limit_weeks: int = 8) -> dict[str, Any]:
        tz, week_start_day = self.get_user_settings(user_id)
        breakdown = self.weekly_breakdown(
            user_id=user_id,
            tz=tz,
            week_start_day=week_start_day,
            limit_weeks=limit_weeks,
        )
        if not breakdown:
            return {
                "breakdown": [],
                "best_week": None,
                "average_seconds": 0,
            }

        best_week = max(breakdown, key=lambda item: item[1])
        average_seconds = int(sum(total for _, total in breakdown) / len(breakdown))
        return {
            "breakdown": breakdown,
            "best_week": best_week,
            "average_seconds": average_seconds,
        }
