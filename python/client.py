import mmap
from multiprocessing.shared_memory import SharedMemory
from typing import Dict, Optional

from wayland import ConnectionManager
from wayland.protocol import *

WIDTH, HEIGHT = 500, 500
MAX_WIDTH, MAX_HEIGHT = 0, 0
STRIDE = WIDTH * 4
POOL_SIZE = STRIDE * HEIGHT * 2  # Double Buffering

WINDOW_TITLE = "WayGUI"

RUNNING = True

shm: Optional[SharedMemory] = None
pool_data: Optional[mmap.mmap] = None

registry: Dict[str, Dict[str, int]] = {}


def main(conn: ConnectionManager):
    pass


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
