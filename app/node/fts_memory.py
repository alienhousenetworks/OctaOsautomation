import os
import sqlite3
from typing import List, Dict, Any, Optional
import datetime

class SQLiteFTSMemory:
    """
    SQLite FTS5 Full-Text Search Memory Engine for OctaOS Local Node Daemon (~/.octaos/memory.db).
    Provides instant, zero-dependency, cross-session recall of terminal logs, system events,
    code snippets, and past agent conversations.
    """
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.expanduser("~/.octaos/memory.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Create main memory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Create FTS5 virtual table for lightning-fast full text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    content,
                    source,
                    category,
                    content='memory_records',
                    content_rowid='id'
                )
            """)
            # Create triggers to sync FTS5 index automatically
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_after_insert AFTER INSERT ON memory_records BEGIN
                    INSERT INTO memory_fts(rowid, content, source, category) 
                    VALUES (new.id, new.content, new.source, new.category);
                END;
            """)
            conn.commit()

    def store(self, source: str, category: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memory_records (source, category, content, metadata_json) VALUES (?, ?, ?, ?)",
                (source, category, content, json.dumps(metadata or {}))
            )
            conn.commit()
            return cursor.lastrowid

    def search(self, query_str: str, limit: int = 10) -> List[Dict[str, Any]]:
        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT r.id, r.source, r.category, r.content, r.metadata_json, r.created_at, fts.rank
                    FROM memory_fts fts
                    JOIN memory_records r ON fts.rowid = r.id
                    WHERE memory_fts MATCH ?
                    ORDER BY fts.rank
                    LIMIT ?
                """, (query_str, limit))
                for row in cursor.fetchall():
                    results.append(dict(row))
            except sqlite3.OperationalError:
                # Fallback to standard LIKE if FTS query syntax error
                cursor.execute("""
                    SELECT id, source, category, content, metadata_json, created_at
                    FROM memory_records
                    WHERE content LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                """, (f"%{query_str}%", limit))
                for row in cursor.fetchall():
                    results.append(dict(row))
        return results

fts_memory = SQLiteFTSMemory()
