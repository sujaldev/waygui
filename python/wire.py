import os
import socket

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
    sock.close()


if __name__ == "__main__":
    main()
