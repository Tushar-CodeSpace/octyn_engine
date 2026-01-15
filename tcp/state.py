from enum import Enum

class TcpMode(str, Enum):
    SERVER = "server"
    CLIENT = "client"

class TcpRuntime:
    mode: TcpMode | None = None
    host: str | None = None
    port: int | None = None

runtime = TcpRuntime()
