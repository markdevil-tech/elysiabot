"""
Persistent memory system using SQLite.
Stores conversations, extracted facts, locations, and schedules.
"""
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 5,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                address TEXT,
                city TEXT,
                latitude REAL,
                longitude REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                event_date DATE,
                event_time TIME,
                recurrence TEXT DEFAULT 'none',
                reminded INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_conv_timestamp ON conversations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(event_date);
        """)
        self.conn.commit()

    # ── Conversations ──────────────────────────────────────────────

    def save_message(self, role: str, content: str):
        self.conn.execute(
            "INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
            (role, content, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_recent_messages(self, limit: int = 50) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT role, content, timestamp FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        messages = [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]
        return messages

    def get_conversation_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM conversations").fetchone()
        return row["cnt"]

    # ── Long-Term Memories ─────────────────────────────────────────

    def save_memory(self, category: str, content: str, importance: int = 5):
        existing = self.conn.execute(
            "SELECT id FROM memories WHERE category = ? AND content = ?",
            (category, content)
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE memories SET importance = ?, updated_at = ? WHERE id = ?",
                (importance, datetime.now().isoformat(), existing["id"])
            )
        else:
            self.conn.execute(
                "INSERT INTO memories (category, content, importance) VALUES (?, ?, ?)",
                (category, content, importance)
            )
        self.conn.commit()

    def get_all_memories(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT category, content, importance FROM memories ORDER BY importance DESC, updated_at DESC"
        ).fetchall()
        return [{"category": r["category"], "content": r["content"], "importance": r["importance"]} for r in rows]

    def search_memories(self, keyword: str) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT category, content FROM memories WHERE content LIKE ?",
            (f"%{keyword}%",)
        ).fetchall()
        return [{"category": r["category"], "content": r["content"]} for r in rows]

    # ── Locations ──────────────────────────────────────────────────

    def save_location(self, name: str, address: str = "", city: str = "",
                      latitude: float = 0.0, longitude: float = 0.0):
        self.conn.execute("""
            INSERT INTO locations (name, address, city, latitude, longitude)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                address = excluded.address,
                city = excluded.city,
                latitude = excluded.latitude,
                longitude = excluded.longitude
        """, (name.lower(), address, city, latitude, longitude))
        self.conn.commit()

    def get_location(self, name: str) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM locations WHERE name = ?", (name.lower(),)
        ).fetchone()
        if row:
            return dict(row)
        return None

    def get_all_locations(self) -> List[Dict]:
        rows = self.conn.execute("SELECT * FROM locations").fetchall()
        return [dict(r) for r in rows]

    # ── Schedules ──────────────────────────────────────────────────

    def add_schedule(self, title: str, event_date: str, event_time: str = "",
                     description: str = "", recurrence: str = "none") -> int:
        cursor = self.conn.execute(
            "INSERT INTO schedules (title, description, event_date, event_time, recurrence) VALUES (?, ?, ?, ?, ?)",
            (title, description, event_date, event_time, recurrence)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_upcoming_schedules(self, days: int = 7) -> List[Dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT * FROM schedules WHERE event_date BETWEEN ? AND ? ORDER BY event_date, event_time",
            (today, future)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_today_schedules(self) -> List[Dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT * FROM schedules WHERE event_date = ? ORDER BY event_time",
            (today,)
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_schedule(self, schedule_id: int) -> bool:
        cursor = self.conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_all_schedules(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM schedules ORDER BY event_date, event_time"
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_reminded(self, schedule_id: int):
        self.conn.execute(
            "UPDATE schedules SET reminded = 1 WHERE id = ?", (schedule_id,)
        )
        self.conn.commit()

    def get_unreminded_schedules(self) -> List[Dict]:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")
        rows = self.conn.execute(
            """SELECT * FROM schedules
               WHERE event_date = ? AND event_time <= ? AND event_time != '' AND reminded = 0
               ORDER BY event_time""",
            (today, current_time)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
