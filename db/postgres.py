import asyncpg
from core.config import DB_CONFIG

pool = None

async def connect():
    global pool
    pool = await asyncpg.create_pool(**DB_CONFIG)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS shipment_data (
            id UUID PRIMARY KEY,
            awb_number TEXT,
            processed_timestamp TIMESTAMP,
            is_sorted BOOLEAN,
            is_uploaded BOOLEAN
        )
        """)

async def close():
    if pool:
        await pool.close()
