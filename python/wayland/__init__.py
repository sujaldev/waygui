import array
import os
import socket
from io import BytesIO
from typing import Iterable, List, Optional, Type, TypeVar

from .client_core import *
from .protocol import WlDisplay

__all__ = [
    "ConnectionManager"
]

T = TypeVar("T", bound="WLObject")


class ConnectionManager:
    def __init__(self, name: str = None):
        self.objects: List[Optional["WLObject"]] = [
            None,  # Object 0 -> null object
            WlDisplay(1, self)  # Object 1 -> wl_display
        ]

        self._sock: Optional[socket.socket] = None
        self._send_buffer = bytes()
        self._recv_buffer = BytesIO()

        self.setup_socket(name)

    @property
    def wl_display(self) -> "WlDisplay":
        # noinspection PyTypeChecker
        return self.objects[1]

    def setup_socket(self, name: str = None):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
        self._sock.settimeout(2.0)

        if name is None:
            name = os.getenv("WAYLAND_DISPLAY", default="wayland-0")

        if not name.startswith("/"):
            xdg_runtime_dir = os.getenv("XDG_RUNTIME_DIR", default=f"/run/user/{os.getuid()}")
            name = f"{xdg_runtime_dir}/{name}"

        self._sock.connect(name)

    def create_object(self, klass: Type[T]) -> T:
        obj = klass(len(self.objects), self)
        self.objects.append(obj)
        return obj

    def parse_response(self):
        header = Header.frombytes(self._recv_buffer)
        if not header:
            return

        obj = self.objects[header.obj_id.value]

        try:
            obj.callbacks[header.opcode](self._recv_buffer.read(header.size))
        except KeyError:
            # noinspection PyTypeHints
            missing_callback_name = obj.EVENTS[header.opcode]
            raise Exception(
                f"Missing {missing_callback_name!r} callback for object {type(obj).__name__!r}"
            )

    def flush(self, fds: Iterable = None):
        if self._send_buffer:
            if fds is None:
                self._sock.send(self._send_buffer)
            else:
                self._sock.sendmsg(
                    [self._send_buffer],
                    [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", fds))]
                )
            del self._send_buffer
            self._send_buffer = bytes()

        try:
            data = self._sock.recv(4096)
        except socket.timeout:
            del self._recv_buffer
            self._recv_buffer = BytesIO()
            return

        data_len = len(data)
        if data_len == 0:
            return

        self._recv_buffer.write(data)
        self._recv_buffer.seek(-data_len, 1)

        while self._recv_buffer.tell() < data_len:
            self.parse_response()

        del self._recv_buffer
        self._recv_buffer = BytesIO()

    def close(self):
        self._sock.close()

    def __enter__(self) -> "ConnectionManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
