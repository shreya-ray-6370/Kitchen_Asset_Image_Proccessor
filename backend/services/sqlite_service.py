import sqlite3
import os
import json
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "db" / "scans.db"
UPLOAD_DIR = BASE_DIR / "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ✅ INIT DB
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scans (
        scan_id TEXT PRIMARY KEY,
        image_path TEXT NOT NULL,
        metadata_payload TEXT,
        condition_payload TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Backward-compatible migration for earlier table shape.
    cursor.execute("PRAGMA table_info(scans)")
    columns = {row[1] for row in cursor.fetchall()}
    if "metadata_payload" not in columns:
        cursor.execute("ALTER TABLE scans ADD COLUMN metadata_payload TEXT")
    if "condition_payload" not in columns:
        cursor.execute("ALTER TABLE scans ADD COLUMN condition_payload TEXT")
    if "created_at" not in columns:
        cursor.execute("ALTER TABLE scans ADD COLUMN created_at TEXT")
        cursor.execute(
            "UPDATE scans SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
        )

    conn.commit()
    conn.close()


# ✅ SAVE IMAGE
def save_scan(scan_id, image_bytes):
    filename = f"{scan_id}.webp"
    filepath = UPLOAD_DIR / filename

    with open(filepath, "wb") as f:
        f.write(image_bytes)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO scans (scan_id, image_path, created_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(scan_id) DO UPDATE SET
            image_path = excluded.image_path
        """,
        (scan_id, str(filepath)),
    )

    conn.commit()
    conn.close()

    return str(filepath)


def get_scan_path(scan_id: str) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT image_path FROM scans WHERE scan_id = ?", (scan_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def save_condition(scan_id: str, condition_payload: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE scans SET condition_payload = ? WHERE scan_id = ?",
        (json.dumps(condition_payload), scan_id),
    )
    conn.commit()
    conn.close()


def save_metadata(scan_id: str, metadata_payload: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE scans SET metadata_payload = ? WHERE scan_id = ?",
        (json.dumps(metadata_payload), scan_id),
    )
    conn.commit()
    conn.close()


def get_metadata_payload(scan_id: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT metadata_payload FROM scans WHERE scan_id = ?", (scan_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return None
    return json.loads(row[0])


def get_condition_payload(scan_id: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT condition_payload FROM scans WHERE scan_id = ?", (scan_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return None
    return json.loads(row[0])


def list_scan_records() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT scan_id, image_path, metadata_payload, condition_payload, created_at
        FROM scans
        ORDER BY datetime(created_at) DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    records: list[dict] = []
    # Backward compatibility: older DB may have 4 columns in query result.
    for row in rows:
        if len(row) == 4:
            scan_id, image_path, condition_payload, created_at = row
            metadata_payload = None
        else:
            scan_id, image_path, metadata_payload, condition_payload, created_at = row
        records.append(
            {
                "scan_id": scan_id,
                "image_path": image_path,
                "metadata_payload": json.loads(metadata_payload) if metadata_payload else None,
                "condition_payload": json.loads(condition_payload) if condition_payload else None,
                "created_at": created_at,
            }
        )
    return records