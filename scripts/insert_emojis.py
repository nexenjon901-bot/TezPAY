"""Emoji IDlarini bazaga kiritish skripti"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.database import engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, text

EMOJIS = {
    "emoji_shop":     "5373052667671093676",
    "emoji_profile":  "5373012449597335010",
    "emoji_balance":  "5271900303745110752",
    "emoji_support":  "5190458330719461749",
    "emoji_referral": "5357080225463149588",
    "emoji_useful":   "5433982607035474385",
}

async def main():
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        for key, value in EMOJIS.items():
            await session.execute(
                text("""
                    INSERT INTO settings (key, value)
                    VALUES (:key, :value)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """),
                {"key": key, "value": value}
            )
            print(f"OK: {key} = {value}")
        await session.commit()
        print("\nBarcha emoji IDlar bazaga yozildi!")

if __name__ == "__main__":
    asyncio.run(main())
