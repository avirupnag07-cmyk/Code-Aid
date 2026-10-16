"""Small SQLite repository for durable investigation records."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .config import Settings


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class InvestigationRepository:
    """SQLite-backed persistence with JSON columns for engine output."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.settings.database_path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS investigations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    sample_id TEXT,
                    source_json TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_investigations_updated ON investigations(updated_at DESC)"
            )

    @staticmethod
    def _row(row: sqlite3.Row, include_results: bool = True) -> Dict[str, Any]:
        source = _loads(row["source_json"], {})
        stored_results = _loads(row["results_json"], {})
        results = stored_results if include_results else None
        item: Dict[str, Any] = {
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "source_type": row["source_type"],
            "sample_id": row["sample_id"],
            "source": source,
            "storage_path": row["storage_path"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_results:
            item["results"] = results or {}
        else:
            # Keep list responses lightweight while preserving the counts the
            # dashboard needs. The previous implementation dropped results
            # entirely and made every investigation look like it had zero
            # findings or hypotheses.
            item["finding_count"] = len((stored_results or {}).get("findings") or [])
            item["hypothesis_count"] = len((stored_results or {}).get("hypotheses") or [])
        return item

    def create(
        self,
        investigation_id: str,
        title: str,
        status: str,
        source_type: str,
        sample_id: Optional[str],
        source: Dict[str, Any],
        results: Dict[str, Any],
        storage_path: Path,
    ) -> Dict[str, Any]:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO investigations
                    (id, title, status, source_type, sample_id, source_json,
                     results_json, storage_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    investigation_id,
                    title,
                    status,
                    source_type,
                    sample_id,
                    _json(source),
                    _json(results),
                    str(storage_path),
                    now,
                    now,
                ),
            )
        return self.get(investigation_id)  # type: ignore[return-value]

    def get(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM investigations WHERE id = ?", (investigation_id,)
            ).fetchone()
        return self._row(row) if row else None

    def list(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM investigations ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (max(1, min(limit, 500)), max(0, offset)),
            ).fetchall()
        return [self._row(row, include_results=False) for row in rows]

    def update(
        self,
        investigation_id: str,
        *,
        status: Optional[str] = None,
        results: Optional[Dict[str, Any]] = None,
        source: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        current = self.get(investigation_id)
        if current is None:
            return None
        next_status = status or current["status"]
        next_results = results if results is not None else current.get("results", {})
        next_source = source if source is not None else current.get("source", {})
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE investigations
                   SET status = ?, source_json = ?, results_json = ?, updated_at = ?
                 WHERE id = ?
                """,
                (next_status, _json(next_source), _json(next_results), utc_now(), investigation_id),
            )
        return self.get(investigation_id)

    def delete(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        existing = self.get(investigation_id)
        if existing is None:
            return None
        with self._connect() as connection:
            connection.execute("DELETE FROM investigations WHERE id = ?", (investigation_id,))
        return existing


# A concise alias is useful to callers that do not need the domain-specific name.
SQLiteStore = InvestigationRepository
