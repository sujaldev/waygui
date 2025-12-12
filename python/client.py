import mmap
from multiprocessing.shared_memory import SharedMemory
from typing import Dict, Optional

from wayland import ConnectionManager
from wayland.protocols.wayland import *

WIDTH, HEIGHT = 500, 500
MAX_WIDTH, MAX_HEIGHT = 0, 0
STRIDE = WIDTH * 4
POOL_SIZE = STRIDE * HEIGHT * 2  # Double Buffering

WINDOW_TITLE = "WayGUI"

RUNNING = True

shm: Optional[SharedMemory] = None
pool_data: Optional[mmap.mmap] = None


class Display(WlDisplay):
    pass


class Registry(WlRegistry):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.registry: Dict[str, Dict[str, int]] = {}

    def on_global(self, name: UInt32 | int, interface: String | str, version: UInt32 | int):
        self.registry[interface.value] = {
            "numeric_name": name.value,
            "version": version.value
        }


def main(conn: ConnectionManager):
    wl_display = conn.create_object(Display)
    wl_registry = conn.create_object(Registry)
    wl_display.get_registry(wl_registry.obj_id)
    conn.flush()
    print(wl_registry.registry)


if __name__ == "__main__":
    try:
        with ConnectionManager() as connection:
            main(connection)
    except KeyboardInterrupt:
        pass
    finally:
        if pool_data:
            pool_data.close()
        if shm:
            shm.unlink()
            shm.close()
