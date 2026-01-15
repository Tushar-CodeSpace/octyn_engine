import asyncio
import threading
from datetime import datetime
import uvicorn

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static
from textual.containers import Vertical, VerticalScroll

from api.app import api
from core.config import API_HOST, API_PORT
from db.postgres import connect, close
from tcp.state import runtime, TcpMode
from tcp import server as tcp_server
from tcp import client as tcp_client
from tcp.cyclic import cyclic
from tui.layout import CSS

ANSI_RESET = "\033[0m"
ANSI_DIM = "\033[2m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[34m"
ANSI_CYAN = "\033[36m"

def run_api():
    uvicorn.run(api, host=API_HOST, port=API_PORT, log_level="warning")


class OctynTUI(App):
    CSS = CSS

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            with VerticalScroll():
                self.log_view = Static("")
                yield self.log_view

            self.input = Input(placeholder="› type command and press enter")
            yield self.input
        yield Footer()

    async def on_mount(self):
        self.input.focus()
        self.log_lines: list[str] = []

        tcp_server.log_cb = self.write_log

        await connect()
        threading.Thread(target=run_api, daemon=True).start()

        self.write_log("● UI started (IDLE)")
        self.write_log("● /start tcp_server <port>")
        self.write_log("● /start tcp_client <host> <port>")
        self.write_log("● /cyclic \"CMD\" on tcp_server <ms>")
        self.write_log("● /cyclic stop")

    def write_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")

        # detect level by prefix symbol
        if msg.startswith("●"):
            color = ANSI_CYAN
        elif msg.startswith("←"):
            color = ANSI_GREEN
        elif msg.startswith("→"):
            color = ANSI_BLUE
        elif msg.startswith("⟳"):
            color = ANSI_YELLOW
        elif msg.startswith("✖"):
            color = ANSI_RED
        else:
            color = ""

        line = (
            f"{ANSI_DIM}[{ts}]{ANSI_RESET} "
            f"{color}{msg}{ANSI_RESET}"
        )

        self.log_lines.append(line)

        if len(self.log_lines) > 500:
            self.log_lines = self.log_lines[-500:]

        self.log_view.update("\n".join(self.log_lines))
        self.log_view.parent.scroll_end(animate=False)

    async def on_input_submitted(self, event):
        msg = event.value.strip()
        self.input.value = ""
        if not msg:
            return

        parts = msg.split()
        cmd = parts[0]

        try:
            # START
            if cmd == "/start":
                if parts[1] == "tcp_server":
                    port = int(parts[2])
                    await tcp_client.stop()
                    await tcp_server.stop()
                    runtime.mode = TcpMode.SERVER
                    runtime.port = port
                    asyncio.create_task(tcp_server.start(port))
                    self.write_log(f"● SERVER started on {port}")
                    return

                if parts[1] == "tcp_client":
                    host, port = parts[2], int(parts[3])
                    await tcp_server.stop()
                    await tcp_client.stop()
                    runtime.mode = TcpMode.CLIENT
                    runtime.host, runtime.port = host, port
                    asyncio.create_task(tcp_client.start(host, port))
                    self.write_log(f"● CLIENT connected {host}:{port}")
                    return

            # STOP
            if cmd == "/stop":
                await cyclic.stop()
                if parts[1] == "tcp_server":
                    await tcp_server.stop()
                    runtime.mode = None
                    return
                if parts[1] == "tcp_client":
                    await tcp_client.stop()
                    runtime.mode = None
                    return

            # RESTART
            if cmd == "/restart":
                await cyclic.stop()
                if parts[1] == "tcp_server":
                    await tcp_server.stop()
                    port = int(parts[2]) if len(parts) > 2 else runtime.port
                    runtime.mode = TcpMode.SERVER
                    runtime.port = port
                    asyncio.create_task(tcp_server.start(port))
                    self.write_log(f"● SERVER restarted on {port}")
                    return

                if parts[1] == "tcp_client":
                    await tcp_client.stop()
                    host = parts[2] if len(parts) > 3 else runtime.host
                    port = int(parts[3]) if len(parts) > 3 else runtime.port
                    runtime.mode = TcpMode.CLIENT
                    runtime.host, runtime.port = host, port
                    asyncio.create_task(tcp_client.start(host, port))
                    self.write_log(f"● CLIENT restarted {host}:{port}")
                    return

            # ---------- CYCLIC ----------
            if cmd == "/cyclic":
                try:
                    # /cyclic stop
                    if len(parts) == 2 and parts[1] == "stop":
                        await cyclic.stop()
                        self.write_log("● CYCLIC stopped")
                        return

                    # Expected: /cyclic "CMD" on tcp_server 5000
                    if '"' not in msg:
                        self.write_log("✖ Invalid cyclic syntax")
                        return

                    # Extract command inside quotes
                    quoted = msg.split('"')
                    command = quoted[1].strip()

                    tail = quoted[2].strip().split()
                    if len(tail) != 3 or tail[0] != "on":
                        self.write_log("✖ Invalid cyclic syntax")
                        return

                    target = tail[1]
                    interval_ms = int(tail[2])

                    if target == "tcp_server":
                        if runtime.mode != TcpMode.SERVER:
                            self.write_log("✖ tcp_server not running")
                            return

                        await cyclic.start(command, TcpMode.SERVER, interval_ms)
                        self.write_log(f"⟳ CYCLIC '{command}' every {interval_ms}ms (SERVER)")
                        return

                    if target == "tcp_client":
                        if runtime.mode != TcpMode.CLIENT:
                            self.write_log("✖ tcp_client not running")
                            return

                        await cyclic.start(command, TcpMode.CLIENT, interval_ms)
                        self.write_log(f"⟳ CYCLIC '{command}' every {interval_ms}ms (CLIENT)")
                        return

                    self.write_log("✖ Unknown cyclic target")
                    return

                except Exception as e:
                    self.write_log(f"✖ {e}")
                    return

            # SEND
            if runtime.mode == TcpMode.SERVER:
                await tcp_server.send(msg)
                return

            if runtime.mode == TcpMode.CLIENT:
                await tcp_client.send(msg)
                return

            self.write_log("✖ No active TCP mode")

        except Exception as e:
            self.write_log(f"✖ {e}")

    async def on_shutdown_request(self):
        await cyclic.stop()
        await tcp_server.stop()
        await tcp_client.stop()
        await close()
