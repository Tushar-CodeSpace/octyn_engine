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
    log(f"● Client connected {addr[0]}:{addr[1]}")

    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            payload = data.decode(errors="ignore").strip()
            log(f"← {addr[0]}:{addr[1]} {payload}")
    finally:
        clients.discard(writer)
        writer.close()
        await writer.wait_closed()
        log(f"● Client disconnected {addr[0]}:{addr[1]}")


async def start(port: int):
    global server_instance
    server_instance = await asyncio.start_server(
        handle_client, "0.0.0.0", port
    )
    log(f"● TCP SERVER started on {port}")
    async with server_instance:
        await server_instance.serve_forever()


async def stop():
    global server_instance
    if server_instance:
        server_instance.close()
        await server_instance.wait_closed()
        server_instance = None
        log("● TCP SERVER stopped")


async def send(msg: str):
    for w in list(clients):
        try:
            w.write((msg + "\n").encode())
            await w.drain()
            log(f"→ {msg}")
        except Exception:
            clients.discard(w)
