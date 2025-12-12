import mmap
from multiprocessing.shared_memory import SharedMemory
from typing import Dict, Optional

from wayland import ConnectionManager
from wayland.protocols.wayland import *
from wayland.protocols.xdg_decoration_unstable_v1 import *
from wayland.protocols.xdg_shell import *

WIDTH, HEIGHT = 500, 500
MAX_WIDTH, MAX_HEIGHT = 0, 0
STRIDE = WIDTH * 4
POOL_SIZE = STRIDE * HEIGHT * 2  # Double Buffering

WINDOW_TITLE = "WayGUI"

RUNNING = True

shm: Optional[SharedMemory] = None
pool_data: Optional[mmap.mmap] = None


def create_shared_memory():
    # Create shared memory for a surface of size `width * height` assuming XRGB8888 format and double buffering.
    global shm
    global pool_data

    shm = SharedMemory(create=True, size=POOL_SIZE)
    # noinspection PyArgumentList,PyUnresolvedReferences,PyProtectedMember
    pool_data = mmap.mmap(
        shm._fd, POOL_SIZE,
        prot=mmap.PROT_READ | mmap.PROT_WRITE,
        flags=mmap.MAP_SHARED
    )

    # Draw checker pattern
    block_size = 63
    for y in range(HEIGHT):
        for x in range(WIDTH):
            offset = (STRIDE * y) + (x * 4)
            pool_data[offset + 3] = 0xFF  # Alpha

            row_inverter = (y // block_size % 2)
            if ((x // block_size) % 2) ^ row_inverter:
                pool_data[offset + 2] = 0x00  # Red
                pool_data[offset + 1] = 0x00  # Green
                pool_data[offset] = 0x00  # Blue
            else:
                pool_data[offset + 2] = 0xFF
                pool_data[offset + 1] = 0xFF
                pool_data[offset] = 0xFF


class Display(WlDisplay):
    def on_error(self, object_id: ObjID | int, code: UInt32 | int, message: String | str):
        obj = self.connection.objects[object_id.value]
        print(f"Error(obj={obj}, code={code.value}): {message.value!r}")


class Registry(WlRegistry):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.registry: Dict[str, Dict[str, int]] = {}

    def on_global(self, name: UInt32 | int, interface: String | str, version: UInt32 | int):
        self.registry[interface.value] = {
            "numeric_name": name.value,
            "version": version.value
        }

    # noinspection PyMethodOverriding
    def bind(self, name: str, obj: WLObject) -> bytes:
        numeric_name = self.registry[name]["numeric_name"]
        version = self.registry[name]["version"]
        return super().bind(numeric_name, name, version, obj.obj_id)


class Compositor(WlCompositor):
    pass


class WlSharedMemory(WlShm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.supported_pixel_formats = []

    def on_format(self, format_: UInt32 | int):
        self.supported_pixel_formats.append(format_)


class WMBase(XdgWmBase):
    def on_ping(self, serial: UInt32 | int):
        self.pong(serial)


class DecorationManager(ZxdgDecorationManagerV1):
    pass


class Surface(WlSurface):
    def on_preferred_buffer_scale(self, factor: Int32 | int):
        print(f"preferred_buffer_scale =", factor.value)

    def on_preferred_buffer_transform(self, factor: Int32 | int):
        print(f"preferred_buffer_transform =", factor.value)


class XDGSurface(XdgSurface):
    def on_configure(self, serial: UInt32 | int):
        self.ack_configure(serial)


class XDGTopLevel(XdgToplevel):
    def on_wm_capabilities(self, capabilities: Array | int):
        print("wm_capabilities =", capabilities)

    def on_configure_bounds(self, width: Int32 | int, height: Int32 | int):
        print(f"max bounds = {width.value}x{height.value}")

    def on_configure(self, width: Int32 | int, height: Int32 | int, states: Array | int):
        print(f"server requests Toplevel configuration = {width.value}x{height.value} with states = {states}")

    def on_close(self):
        global RUNNING
        RUNNING = False


class TopLevelDecorationManager(ZxdgToplevelDecorationV1):
    def on_configure(self, mode: UInt32 | int):
        print("TopLevel Decoration Manager mode =", mode.value)


class WLSharedMemoryPool(WlShmPool):
    pass


def main(conn: ConnectionManager):
    wl_display = conn.create_object(Display)
    wl_registry = conn.create_object(Registry)
    wl_display.get_registry(wl_registry.obj_id)
    conn.flush()
    print(wl_registry.registry)

    wl_compositor = conn.create_object(Compositor)
    wl_registry.bind("wl_compositor", wl_compositor)

    wl_shm = conn.create_object(WlSharedMemory)
    wl_registry.bind("wl_shm", wl_shm)

    xdg_wm_base = conn.create_object(WMBase)
    wl_registry.bind("xdg_wm_base", xdg_wm_base)

    xdg_decoration_manager = conn.create_object(DecorationManager)
    wl_registry.bind("zxdg_decoration_manager_v1", xdg_decoration_manager)

    wl_surface = conn.create_object(Surface)
    wl_compositor.create_surface(wl_surface.obj_id)

    xdg_surface = conn.create_object(XDGSurface)
    xdg_wm_base.get_xdg_surface(xdg_surface.obj_id, wl_surface.obj_id)

    xdg_toplevel = conn.create_object(XDGTopLevel)
    xdg_surface.get_toplevel(xdg_toplevel.obj_id)

    xdg_toplevel_decoration = conn.create_object(TopLevelDecorationManager)
    xdg_decoration_manager.get_toplevel_decoration(xdg_toplevel_decoration.obj_id, xdg_toplevel.obj_id)

    xdg_toplevel.set_title(WINDOW_TITLE)

    wl_surface.commit()

    create_shared_memory()
    wl_shm_pool = conn.create_object(WLSharedMemoryPool)
    wl_shm.create_pool(wl_shm_pool.obj_id, 0, POOL_SIZE)

    wl_buffer1 = conn.create_object(WlBuffer)
    wl_shm_pool.create_buffer(wl_buffer1.obj_id, 0, WIDTH, HEIGHT, STRIDE, 1)  # xrgb8888

    # noinspection PyProtectedMember,PyUnresolvedReferences
    conn.flush([shm._fd])

    wl_surface.attach(wl_buffer1.obj_id, x=0, y=0)

    wl_surface.commit()

    while RUNNING:
        conn.flush()


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
