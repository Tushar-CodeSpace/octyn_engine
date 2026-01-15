import asyncio
from tcp.server import log

writer = None

async def start(host: str, port: int):
    global writer
    reader, writer = await asyncio.open_connection(host, port)
    log(f"[SYSTEM] TCP CLIENT connected to {host}:{port}")

async def stop():
    global writer
    if writer:
        writer.close()
        await writer.wait_closed()
        writer = None
        log("[SYSTEM] TCP CLIENT stopped")

async def send(msg: str):
    if writer:
        writer.write((msg + "\n").encode())
        await writer.drain()
