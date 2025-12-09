import os
import socket
from io import BytesIO

import wl_primitives as wl


def wl_display_get_registry(sock: socket.socket) -> BytesIO:
    msg = wl.Message(
        wl.Header(
            obj_id=1,  # wl_display is implicitly assumed to be object id 1
            opcode=1,  # wl_display::get_registry(newId)
        ),
        [wl.NewID(2)]
    ).serialize()

    sock.send(msg)

    data = sock.recv(4096)

    return BytesIO(data)


def setup_socket(name: str = None):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)

    if name is None:
        name = os.getenv("WAYLAND_DISPLAY", default="wayland-0")

    if not name.startswith("/"):
        xdg_runtime_dir = os.getenv("XDG_RUNTIME_DIR", default=f"/run/user/{os.getuid()}")
        name = f"{xdg_runtime_dir}/{name}"

    sock.connect(name)
    return sock


def main():
    sock = setup_socket()
    data = wl_display_get_registry(sock)

    header = wl.Header.frombytes(data)
    sock.close()


if __name__ == "__main__":
    main()
