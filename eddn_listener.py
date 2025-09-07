import asyncio
import json
import sqlite3
import zlib
from typing import Iterable

import websocket

BGS_SCHEMAS: Iterable[str] = ("factionState", "journal")


def _run_listener(db_path: str) -> None:
    """Run the EDDN websocket listener and persist filtered data."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bgs_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faction TEXT,
            system TEXT,
            influence REAL,
            state TEXT,
            timestamp TEXT
        )
        """
    )
    conn.commit()

    def on_message(ws, message: bytes) -> None:  # type: ignore[override]
        try:
            if isinstance(message, str):
                message = message.encode("utf-8")
            data = zlib.decompress(message, 16 + zlib.MAX_WBITS)
            payload = json.loads(data)
            schema = payload.get("$schemaRef", "")
            if not any(key in schema for key in BGS_SCHEMAS):
                return
            msg = payload.get("message", {})
            faction = msg.get("faction") or msg.get("Faction")
            system = msg.get("StarSystem") or msg.get("system")
            influence = msg.get("influence")
            state = msg.get("state") or msg.get("State")
            timestamp = (
                msg.get("timestamp")
                or msg.get("eventTime")
                or msg.get("eventTimestamp")
            )
            conn.execute(
                """
                INSERT INTO bgs_events (faction, system, influence, state, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (faction, system, influence, state, timestamp),
            )
            conn.commit()
        except Exception as exc:  # pragma: no cover - logging only
            print(f"[ERROR] Failed to process EDDN message: {exc}")

    ws = websocket.WebSocketApp(
        "wss://eddn.edcd.io:443",
        on_message=on_message,
    )
    ws.run_forever()


async def eddn_listener(db_path: str = "eddn_data.db") -> None:
    """Coroutine that listens to EDDN and writes BGS updates to a database."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_listener, db_path)
