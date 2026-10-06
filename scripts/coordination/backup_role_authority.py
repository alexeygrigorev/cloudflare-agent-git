#!/usr/bin/env python3
import sqlite3
import hashlib
import argparse
import os

def backup_database(source_path: str, dest_path: str) -> dict:
    """Safely backs up a SQLite database using the online backup API."""
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source database not found: {source_path}")

    # Connect to source and destination
    src = sqlite3.connect(source_path)
    dst = sqlite3.connect(dest_path)
    
    with src, dst:
        src.backup(dst)

    # Compute SHA-256 of the backup file
    sha256 = hashlib.sha256()
    with open(dest_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
            
    digest = sha256.hexdigest()
    
    # Read generation if exists
    dst.row_factory = sqlite3.Row
    cursor = dst.cursor()
    try:
        cursor.execute("SELECT value FROM authority_meta WHERE key = 'generation'")
        row = cursor.fetchone()
        generation = row['value'] if row else "unknown"
    except sqlite3.OperationalError:
        generation = "unknown"

    src.close()
    dst.close()
    
    return {
        "status": "success",
        "sha256": digest,
        "generation": generation,
        "dest": dest_path
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup role authority DB")
    parser.add_argument("--source", required=True, help="Path to source SQLite database")
    parser.add_argument("--dest", required=True, help="Path to destination SQLite database")
    args = parser.parse_args()
    
    result = backup_database(args.source, args.dest)
    print(f"Backup complete: {result['dest']}")
    print(f"SHA-256: {result['sha256']}")
    print(f"Generation: {result['generation']}")
