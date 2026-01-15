import asyncio
from tcp.state import runtime, TcpMode
from tcp import server as tcp_server
from tcp import client as tcp_client

class CyclicManager:
    def __init__(self):
        self.task = None
        self.command = None
        self.interval_ms = None
        self.target = None

    async def _runner(self):
        interval = self.interval_ms / 1000
        while True:
            if self.target == TcpMode.SERVER:
                await tcp_server.send(self.command)
            elif self.target == TcpMode.CLIENT:
                await tcp_client.send(self.command)

            tcp_server.log(f"[CYCLIC] {self.command}")
            await asyncio.sleep(interval)

    async def start(self, command: str, target: TcpMode, interval_ms: int):
        await self.stop()

        self.command = command
        self.target = target
        self.interval_ms = interval_ms

        self.task = asyncio.create_task(self._runner())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
            tcp_server.log("[SYSTEM] Cyclic stopped")

cyclic = CyclicManager()
