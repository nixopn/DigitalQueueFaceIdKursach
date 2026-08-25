from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from terminal.face_engine import bytes_to_embedding, embedding_to_bytes


class QueueService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def stored_embeddings(self) -> list[tuple[int, object]]:
        rows = self.conn.execute("SELECT id, embedding FROM clients").fetchall()
        return [(row["id"], bytes_to_embedding(row["embedding"])) for row in rows]

    def register_client(self, embedding) -> int:
        cur = self.conn.execute(
            "INSERT INTO clients (embedding) VALUES (?)",
            (embedding_to_bytes(embedding),),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def touch_client(self, client_id: int) -> None:
        self.conn.execute(
            "UPDATE clients SET last_visit = datetime('now') WHERE id = ?",
            (client_id,),
        )
        self.conn.commit()

    def next_number(self) -> int:
        row = self.conn.execute("SELECT MAX(queue_number) AS n FROM queue").fetchone()
        return int(row["n"] or 0) + 1

    def active_for_client(self, client_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT * FROM queue
            WHERE client_id = ? AND status IN ('waiting', 'serving')
            ORDER BY queue_number LIMIT 1
            """,
            (client_id,),
        ).fetchone()

    def enqueue(self, client_id: int) -> sqlite3.Row:
        existing = self.active_for_client(client_id)
        if existing:
            return existing
        number = self.next_number()
        cur = self.conn.execute(
            "INSERT INTO queue (client_id, queue_number, status) VALUES (?, ?, 'waiting')",
            (client_id, number),
        )
        self.conn.commit()
        return self.conn.execute("SELECT * FROM queue WHERE id = ?", (cur.lastrowid,)).fetchone()

    def attach_pending_order(self, client_id: int, queue_id: int) -> list[dict]:
        row = self.conn.execute("SELECT items_json FROM pending_cart WHERE id = 1").fetchone()
        if not row:
            return []
        items = json.loads(row["items_json"])
        if not items:
            return []
        self.conn.execute(
            "INSERT INTO orders (client_id, queue_id, items_json) VALUES (?, ?, ?)",
            (client_id, queue_id, json.dumps(items, ensure_ascii=False)),
        )
        self.conn.execute("DELETE FROM pending_cart WHERE id = 1")
        self.conn.commit()
        return items

    def set_pending_cart(self, items: list[dict]) -> None:
        payload = json.dumps(items, ensure_ascii=False)
        self.conn.execute(
            """
            INSERT INTO pending_cart (id, items_json, updated_at)
            VALUES (1, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET items_json = excluded.items_json, updated_at = datetime('now')
            """,
            (payload,),
        )
        self.conn.commit()

    def pending_cart(self) -> list[dict]:
        row = self.conn.execute("SELECT items_json FROM pending_cart WHERE id = 1").fetchone()
        return json.loads(row["items_json"]) if row else []

    def position(self, queue_number: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS c FROM queue
            WHERE status = 'waiting' AND queue_number < ?
            """,
            (queue_number,),
        ).fetchone()
        return int(row["c"])

    def snapshot(self) -> dict:
        waiting = self.conn.execute(
            """
            SELECT q.*, c.last_visit,
                   (SELECT items_json FROM orders o WHERE o.queue_id = q.id ORDER BY o.id DESC LIMIT 1) AS items_json
            FROM queue q
            JOIN clients c ON c.id = q.client_id
            WHERE q.status IN ('waiting', 'serving')
            ORDER BY q.queue_number
            """
        ).fetchall()
        stats = self.conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM clients) AS clients,
              (SELECT COUNT(*) FROM queue WHERE status = 'waiting') AS waiting,
              (SELECT COUNT(*) FROM queue WHERE status = 'serving') AS serving,
              (SELECT COUNT(*) FROM queue WHERE status = 'done') AS done,
              (SELECT COUNT(*) FROM orders) AS orders
            """
        ).fetchone()
        events = self.conn.execute(
            "SELECT kind, payload, created_at FROM events ORDER BY id DESC LIMIT 40"
        ).fetchall()
        by_hour = self.conn.execute(
            """
            SELECT strftime('%H', created_at) AS hour, COUNT(*) AS c
            FROM queue GROUP BY hour ORDER BY hour
            """
        ).fetchall()
        return {
            "queue": [_queue_item(r) for r in waiting],
            "stats": dict(stats),
            "events": [dict(e) for e in events],
            "hourly": [{"hour": r["hour"], "count": r["c"]} for r in by_hour],
            "pending_cart": self.pending_cart(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def serve(self, queue_id: int) -> None:
        self.conn.execute(
            "UPDATE queue SET status = 'done', served_at = datetime('now') WHERE id = ?",
            (queue_id,),
        )
        self.conn.commit()

    def remove(self, queue_id: int) -> None:
        self.conn.execute("UPDATE queue SET status = 'cancelled' WHERE id = ?", (queue_id,))
        self.conn.commit()

    def reset(self) -> None:
        self.conn.execute("UPDATE queue SET status = 'cancelled' WHERE status IN ('waiting', 'serving')")
        self.conn.execute("DELETE FROM pending_cart")
        self.conn.commit()

    def log(self, kind: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO events (kind, payload) VALUES (?, ?)",
            (kind, json.dumps(payload, ensure_ascii=False)),
        )
        self.conn.commit()


def _queue_item(row: sqlite3.Row) -> dict:
    items = json.loads(row["items_json"]) if row["items_json"] else []
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "queue_number": row["queue_number"],
        "status": row["status"],
        "created_at": row["created_at"],
        "last_visit": row["last_visit"],
        "items": items,
    }
