import asyncio

clients = set()
server_instance = None
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
            log(f"← {addr[0]}:{addr[1]} {data.decode(errors='ignore').strip()}")
    finally:
        clients.discard(writer)
        writer.close()
        await writer.wait_closed()
        log(f"[SYSTEM] Client disconnected {addr}")

async def start(port: int):
    global server_instance
    server_instance = await asyncio.start_server(
        handle_client, "0.0.0.0", port
    )
    log(f"[SYSTEM] TCP SERVER started on :{port}")
    async with server_instance:
        await server_instance.serve_forever()

async def stop():
    global server_instance
    if server_instance:
        server_instance.close()
        await server_instance.wait_closed()
        server_instance = None
        log("[SYSTEM] TCP SERVER stopped")

async def send(msg: str):
    for w in list(clients):
        try:
            w.write((msg + "\n").encode())
            await w.drain()
        except:
            clients.discard(w)
