import sqlite3
import os
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
        image_path TEXT NOT NULL
    )
    """)

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
        "INSERT OR REPLACE INTO scans (scan_id, image_path) VALUES (?, ?)",
        (scan_id, str(filepath))
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