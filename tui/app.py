import asyncio
import threading
import uvicorn

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical

from api.app import api
from core.config import API_HOST, API_PORT
from db.postgres import connect, close
from tcp.state import runtime, TcpMode
from tcp.cyclic import cyclic
from tcp import server as tcp_server
from tcp import client as tcp_client
from tui.layout import CSS


def run_api():
    uvicorn.run(api, host=API_HOST, port=API_PORT, log_level="warning")


class OctynTUI(App):
    CSS = CSS

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            self.log_view = RichLog(auto_scroll=True, markup=True, wrap=False)
            yield self.log_view
            self.input = Input(placeholder="› type command and press enter")
            yield self.input
        yield Footer()

    async def on_mount(self):
        self.input.focus()
        self.log_view.write("[bold green]UI started (IDLE)[/bold green]\n")

        tcp_server.log_cb = self.write_log

        await connect()
        threading.Thread(target=run_api, daemon=True).start()

        self.write_log("[SYSTEM] /start tcp_server <port>")
        self.write_log("[SYSTEM] /start tcp_client <host> <port>")
        self.write_log("[SYSTEM] /cyclic \"CMD\" on tcp_server <ms>")
        self.write_log("[SYSTEM] /cyclic \"CMD\" on tcp_client <ms>")
        self.write_log("[SYSTEM] /cyclic stop")


    def write_log(self, msg: str):
        color = {
            "[RX]": "green",
            "[TX]": "cyan",
            "[SYSTEM]": "yellow",
            "[ERROR]": "red",
        }
        for k, c in color.items():
            if msg.startswith(k):
                self.log_view.write(f"[{c}]{msg}[/{c}]\n")
                return
        self.log_view.write(msg + "\n")

    async def on_input_submitted(self, event):
        msg = event.value.strip()
        self.input.value = ""
        parts = msg.split()
        if not parts:
            return

        cmd = parts[0]

        try:
            # ---------- START ----------
            if cmd == "/start":
                if parts[1] == "tcp_server":
                    port = int(parts[2])
                    await tcp_client.stop()
                    await tcp_server.stop()
                    runtime.mode = TcpMode.SERVER
                    runtime.port = port
                    asyncio.create_task(tcp_server.start(port))
                    self.write_log(f"[SYSTEM] TCP SERVER started on {port}")
                    return

                if parts[1] == "tcp_client":
                    host, port = parts[2], int(parts[3])
                    await tcp_server.stop()
                    await tcp_client.stop()
                    runtime.mode = TcpMode.CLIENT
                    runtime.host, runtime.port = host, port
                    asyncio.create_task(tcp_client.start(host, port))
                    self.write_log(f"[SYSTEM] TCP CLIENT started {host}:{port}")
                    return

            # ---------- STOP ----------
            if cmd == "/stop":
                if parts[1] == "tcp_server":
                    await cyclic.stop()
                    await tcp_server.stop()
                    runtime.mode = None
                    self.write_log("[SYSTEM] TCP SERVER stopped")
                    return

                if parts[1] == "tcp_client":
                    await cyclic.stop()
                    await tcp_client.stop()
                    runtime.mode = None
                    self.write_log("[SYSTEM] TCP CLIENT stopped")
                    return

            # ---------- RESTART ----------
            if cmd == "/restart":
                if parts[1] == "tcp_server":
                    await tcp_server.stop()
                    port = int(parts[2]) if len(parts) > 2 else runtime.port
                    if not port:
                        self.write_log("[ERROR] No previous server port")
                        return
                    runtime.mode = TcpMode.SERVER
                    runtime.port = port
                    asyncio.create_task(tcp_server.start(port))
                    self.write_log(f"[SYSTEM] TCP SERVER restarted on {port}")
                    return

                if parts[1] == "tcp_client":
                    await tcp_client.stop()
                    if len(parts) > 3:
                        host, port = parts[2], int(parts[3])
                    else:
                        host, port = runtime.host, runtime.port
                    if not host or not port:
                        self.write_log("[ERROR] No previous client config")
                        return
                    runtime.mode = TcpMode.CLIENT
                    runtime.host, runtime.port = host, port
                    asyncio.create_task(tcp_client.start(host, port))
                    self.write_log(f"[SYSTEM] TCP CLIENT restarted {host}:{port}")
                    return

            # ---------- CYCLIC ----------
            if cmd == "/cyclic":
                try:
                    # /cyclic stop
                    if parts[1] == "stop":
                        await cyclic.stop()
                        self.write_log("[SYSTEM] Cyclic command stopped")
                        return

                    # /cyclic "RHINO" on tcp_server 10000
                    raw = msg.split('"')
                    if len(raw) < 3:
                        self.write_log("[ERROR] Invalid cyclic syntax")
                        return

                    command = raw[1]
                    tail = raw[2].strip().split()

                    if tail[0] != "on":
                        self.write_log("[ERROR] Expected 'on'")
                        return

                    mode = tail[1]
                    interval_ms = int(tail[2])

                    if mode == "tcp_server":
                        if runtime.mode != TcpMode.SERVER:
                            self.write_log("[ERROR] tcp_server not running")
                            return
                        await cyclic.start(command, TcpMode.SERVER, interval_ms)
                        self.write_log(
                            f"[SYSTEM] Cyclic '{command}' on SERVER every {interval_ms}ms"
                        )
                        return

                    if mode == "tcp_client":
                        if runtime.mode != TcpMode.CLIENT:
                            self.write_log("[ERROR] tcp_client not running")
                            return
                        await cyclic.start(command, TcpMode.CLIENT, interval_ms)
                        self.write_log(
                            f"[SYSTEM] Cyclic '{command}' on CLIENT every {interval_ms}ms"
                        )
                        return

                    self.write_log("[ERROR] Unknown cyclic target")

                except Exception as e:
                    self.write_log(f"[ERROR] {e}")
                return


            # ---------- SEND ----------
            if runtime.mode == TcpMode.SERVER:
                await tcp_server.send(msg)
                self.write_log(f"[TX] {msg}")
                return

            if runtime.mode == TcpMode.CLIENT:
                await tcp_client.send(msg)
                self.write_log(f"[TX] {msg}")
                return

            self.write_log("[ERROR] No active TCP mode")

        except Exception as e:
            self.write_log(f"[ERROR] {e}")

    async def on_shutdown_request(self):
        await close()
