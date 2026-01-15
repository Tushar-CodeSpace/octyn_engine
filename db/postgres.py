import asyncpg

pool = None

async def connect():
    global pool
    pool = await asyncpg.create_pool(
        host="127.0.0.1",
        port=5432,
        database="octyn_engine_db",
        user="postgres",
        password="postgres",
    )

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
