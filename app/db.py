import aiosqlite
import os
import glob
from contextlib import asynccontextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = BASE_DIR / "migrations"

def _db_path():
    # Read DATABASE_URL via getenv so .env.local can override in demo setups
    return os.getenv('DATABASE_URL', 'sqlite:///./bot.db').replace('sqlite:///', '')

async def init_db():
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    async with aiosqlite.connect(_db_path()) as db:

        if not files:
            # fallback for CI/tests
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_id INTEGER,
                master_id INTEGER,
                date TEXT,
                time TEXT,
                name TEXT,
                phone TEXT,
                status TEXT DEFAULT 'active'
            );
            """)
        else:
            for p in files:
                sql = p.read_text(encoding="utf-8")
                try:
                    await db.executescript(sql)
                except Exception as e:
                    msg = str(e).lower()
                    if 'duplicate column' in msg or 'already exists' in msg:
                        continue
                    raise

        await db.commit()

        # Clean up old bookings
        from datetime import datetime
        today = datetime.now().date().isoformat()
        await db.execute('DELETE FROM bookings WHERE NOT (date >= ? AND status = "scheduled")', (today,))
        await db.commit()

@asynccontextmanager
async def get_db():
    conn = await aiosqlite.connect(_db_path())
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()
