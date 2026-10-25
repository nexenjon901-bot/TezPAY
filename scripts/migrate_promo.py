import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from db.database import engine
from db.models.base import Base
import db.models  # load all models


async def run_migrations():
    async with engine.begin() as conn:
        print("1. Creating promo_codes and promo_code_usages tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("   OK - Tables created or verified.")

        print("2. Adding PROMO_CODE to transactiontype enum if not present...")
        try:
            await conn.execute(text("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'PROMO_CODE';"))
            print("   OK - Enum value verified.")
        except Exception as e:
            print(f"   Note: {e}")

    print("\nMigration finished successfully!")


if __name__ == "__main__":
    asyncio.run(run_migrations())
