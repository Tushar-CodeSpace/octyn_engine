import asyncio
from core.config import TCP_HOST, TCP_PORT, RHINO_CMD, RHINO_INTERVAL

clients = set()
log_cb = None

def log(msg: str):
    if log_cb:
        log_cb(msg)

async def handle_client(reader, writer):
    addr = writer.get_extra_info("peername")
    clients.add(writer)
    log(f"[SYSTEM] Client connected {addr}")

    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            log(f"[RX] {addr}: {data.decode(errors='ignore').strip()}")
    finally:
        clients.discard(writer)
        writer.close()
        await writer.wait_closed()
        log(f"[SYSTEM] Client disconnected {addr}")

async def send(msg: str):
    dead = []
    for w in clients:
        try:
            w.write((msg + "\n").encode())
            await w.drain()
        except:
            dead.append(w)

    for d in dead:
        clients.discard(d)

    if clients:
        log(f"[TX] {msg} → {len(clients)} client(s)")

async def rhino_loop():
    while True:
        await send(RHINO_CMD)
        await asyncio.sleep(RHINO_INTERVAL)

async def start():
    server = await asyncio.start_server(handle_client, TCP_HOST, TCP_PORT)
    log(f"[SYSTEM] TCP server started on :{TCP_PORT}")
    async with server:
        await server.serve_forever()
