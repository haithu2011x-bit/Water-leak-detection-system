"""Online-safe SQLite backup using SQLite's backup API.

Copies a consistent snapshot without shutting down the MQTT collector.
Never edits, deletes or overwrites the source database.
"""
from __future__ import annotations
import argparse
import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "water.db"
DEST_DIR = ROOT / "data" / "backups"


def backup_database(source=SOURCE, destination=None):
    src = Path(source).resolve()
    if not src.is_file():
        raise FileNotFoundError("SQLite source does not exist: " + str(src))
    if destination is None:
        name = "water_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".db"
        dest = DEST_DIR / name
    else:
        dest = Path(destination)
    dest = dest.resolve()
    if src == dest:
        raise ValueError("Cannot overwrite the source database")
    if dest.exists() or Path(str(dest) + ".partial").exists():
        raise FileExistsError("Backup already exists; refusing to overwrite: " + str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(dest) + ".partial")
    try:
        with closing(sqlite3.connect(src.as_uri() + "?mode=ro", uri=True, timeout=10)) as reader:
            with closing(sqlite3.connect(tmp, timeout=10)) as writer:
                reader.backup(writer, pages=50, sleep=0.1)
                result = writer.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    raise RuntimeError("SQLite backup integrity_check failed: " + str(result))
                writer.commit()
        tmp.replace(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    digest = hashlib.sha256()
    with dest.open("rb") as file:
        for part in iter(lambda: file.read(1024*1024), b""):
            digest.update(part)
    return {"path": str(dest), "bytes": dest.stat().st_size, "sha256": digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(SOURCE))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    result = backup_database(args.source, args.output)
    print("Backup completed (independent SQLite snapshot):")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
