import asyncio
import threading
import uvicorn

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical

from api.app import api
from core.config import API_HOST, API_PORT
from db.postgres import connect, close
from tcp import server
from tui.layout import CSS


def run_api():
    uvicorn.run(api, host=API_HOST, port=API_PORT, log_level="warning")


class OctynTUI(App):
    CSS = CSS

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            self.log_view = RichLog(
                auto_scroll=True,
                markup=True,
                wrap=False
            )
            yield self.log_view

            self.input = Input(
                placeholder="› type command and press enter"
            )
            yield self.input
        yield Footer()

    async def on_mount(self):
        self.input.focus()
        self.log_view.write("[bold green]UI started[/bold green]\n")

        server.log_cb = self.write_log

        try:
            await connect()
            self.write_log("[SYSTEM] Database connected")

            asyncio.create_task(server.start())
            asyncio.create_task(server.rhino_loop())

            threading.Thread(target=run_api, daemon=True).start()

            self.write_log("[SYSTEM] TCP :3001 | API :8000 | RHINO every 10s")

        except Exception as e:
            self.log_view.write(f"[bold red]FATAL:[/bold red] {e}\n")

    def write_log(self, msg: str):
        if msg.startswith("[RX]"):
            self.log_view.write(f"[green]{msg}[/green]\n")
        elif msg.startswith("[TX]"):
            self.log_view.write(f"[cyan]{msg}[/cyan]\n")
        elif msg.startswith("[ERROR]"):
            self.log_view.write(f"[bold red]{msg}[/bold red]\n")
        elif msg.startswith("[SYSTEM]"):
            self.log_view.write(f"[bold yellow]{msg}[/bold yellow]\n")
        else:
            self.log_view.write(msg + "\n")

    async def on_input_submitted(self, event):
        msg = event.value.strip()
        if msg:
            await server.send(msg)
            self.log_view.write(f"[cyan][TX-MANUAL][/cyan] {msg}\n")
        self.input.value = ""

    async def on_shutdown_request(self):
        await close()
