import array
import os
import mmap
import socket
from functools import partial
from io import BytesIO
from multiprocessing.shared_memory import SharedMemory
from typing import Dict, Iterable, Optional

import wl_util as wl

WIDTH, HEIGHT = 500, 500
STRIDE = WIDTH * 4
POOL_SIZE = STRIDE * HEIGHT * 2  # Double Buffering

WINDOW_TITLE = "WayGUI"

RUNNING = True

sock: Optional[socket.socket] = None
shm: Optional[SharedMemory] = None
pool_data: Optional[mmap.mmap] = None
send_buffer = bytes()
recv_buffer = BytesIO()

interface = wl.build_interface()
xdg_interface = wl.build_interface(path="/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml")
interface.update(xdg_interface)
objects = [
    None,
    wl.WLObject(wl.ObjID(1), "wl_display", interface["wl_display"])
]

global_objs: Dict[str, Dict[str, int]] = {}


def write_request(wl_object: wl.WLObject, wl_request_name, **kwargs):
    global send_buffer

    request = wl_object.interface.requests[wl_request_name]
    header = wl.Header(wl_object.obj_id, request.opcode)
    args = []
    for arg in request.args:
        arg_obj = arg.type_(kwargs[arg.name])
        if arg.type_ == wl.NewID:
            new_id = kwargs[arg.name]
            if arg.new_interface is None:
                preceding_interface_string = args[-2].value
                new_interface = interface[preceding_interface_string]
            else:
                new_interface = interface[arg.new_interface]
            new_obj = wl.WLObject(wl.ObjID(new_id), new_interface.name, new_interface)
            objects.insert(new_id, new_obj)

        args.append(arg_obj)

    message = wl.Message(header, args)

    send_buffer += message.serialize()


def setup_socket(name: str = None):
    global sock
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
    sock.settimeout(2.0)

    if name is None:
        name = os.getenv("WAYLAND_DISPLAY", default="wayland-0")

    if not name.startswith("/"):
        xdg_runtime_dir = os.getenv("XDG_RUNTIME_DIR", default=f"/run/user/{os.getuid()}")
        name = f"{xdg_runtime_dir}/{name}"

    sock.connect(name)


def flush(fds: Iterable = None):
    global send_buffer
    global recv_buffer

    if send_buffer:
        if fds is None:
            sock.send(send_buffer)
        else:
            sock.sendmsg(
                [send_buffer],
                [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", fds))]
            )
        del send_buffer
        send_buffer = bytes()

    try:
        data = sock.recv(4096)
    except socket.timeout:
        del recv_buffer
        recv_buffer = BytesIO()
        return

    data_len = len(data)
    if data_len == 0:
        return

    recv_buffer.write(data)
    recv_buffer.seek(-data_len, 1)

    while recv_buffer.tell() < data_len:
        parse_response()

    del recv_buffer
    recv_buffer = BytesIO()


def parse_response():
    global recv_buffer

    header = wl.Header.frombytes(recv_buffer)
    if not header:
        return
    obj = objects[header.obj_id.value]
    kwarg_list = {}
    for arg in obj.interface.events[header.opcode].args:
        kwarg_list[arg.name] = arg.type_.frombytes(recv_buffer)
    try:
        obj.callbacks[header.opcode](**kwarg_list)
    except KeyError:
        missing_callback_name = obj.interface.events[header.opcode].name
        raise Exception(
            f"Missing {missing_callback_name!r} callback for object {obj.name!r}"
        )


def wl_registry_global_event(**kwargs):
    name, _interface, version = kwargs.values()
    global_objs[_interface.value] = {
        "name": name.value,
        "version": version.value,
    }


def wl_display_error(**kwargs):
    raise Exception(
        f"error {kwargs['code'].value} {objects[kwargs['object_id'].value]}: {kwargs['message'].value}"
    )


def xdg_wm_base_pong(xdg_wm_base: wl.WLObject, serial: wl.UInt32):
    global send_buffer

    write_request(
        xdg_wm_base, "pong",
        serial=serial.value
    )


def stop():
    global RUNNING
    RUNNING = False


def create_shared_memory():
    # Create shared memory for a surface of size `width * height` assuming XRGB8888 format and double buffering.
    global shm
    global pool_data

    shm = SharedMemory(create=True, size=POOL_SIZE)
    # noinspection PyUnresolvedReferences,PyProtectedMember
    pool_data = mmap.mmap(
        shm._fd, POOL_SIZE,
        prot=mmap.PROT_READ | mmap.PROT_WRITE,
        flags=mmap.MAP_SHARED
    )


def main():
    global recv_buffer

    setup_socket()
    wl_display = objects[1]
    wl_display.set_callback("error", wl_display_error)
    write_request(wl_display, "get_registry", registry=len(objects))
    wl_registry = objects[2]
    wl_registry.callbacks[wl_registry.interface.events["global"].opcode] = wl_registry_global_event

    flush()

    # wl_registry::bind("wl_compositor", 3)
    write_request(
        wl_registry, "bind",
        name=global_objs["wl_compositor"]["name"],
        new_interface_name="wl_compositor",
        new_interface_version=global_objs["wl_compositor"]["version"],
        id=(new_id := len(objects))
    )
    wl_compositor = objects[new_id]

    # wl_registry::bind("wl_shm", "wl_shm", 6, new_id)
    write_request(
        wl_registry, "bind",
        name=global_objs["wl_shm"]["name"],
        new_interface_name="wl_shm",
        new_interface_version=global_objs["wl_shm"]["version"],
        id=(new_id := len(objects))
    )
    wl_shm = objects[new_id]
    wl_shm.set_callback("format", lambda **kwargs: None)  # we assume format to be 0x01 (xrgb8888)

    # wl_registry::bind("xdg_wm_base", "xdg_wm_base", 6, new_id)
    write_request(
        wl_registry, "bind",
        name=global_objs["xdg_wm_base"]["name"],
        new_interface_name="xdg_wm_base",
        new_interface_version=global_objs["xdg_wm_base"]["version"],
        id=(new_id := len(objects))
    )
    xdg_wm_base = objects[new_id]
    xdg_wm_base.set_callback("ping", partial(xdg_wm_base_pong, xdg_wm_base))

    flush()

    # wl_compositor::create_surface(new_id)
    write_request(
        wl_compositor, "create_surface",
        id=(new_id := len(objects))
    )
    wl_surface = objects[new_id]
    wl_surface.set_callback('preferred_buffer_scale')
    wl_surface.set_callback('preferred_buffer_transform')

    # xdg_wm_base::get_xdg_surface(new_id, surface=wl_surface)
    write_request(
        xdg_wm_base, "get_xdg_surface",
        id=(new_id := len(objects)),
        surface=wl_surface.obj_id.value
    )
    xdg_surface = objects[new_id]
    xdg_surface.set_callback("configure")

    # xdg_surface::get_toplevel(new_id)
    write_request(
        xdg_surface, "get_toplevel",
        id=(new_id := len(objects)),
    )
    xdg_toplevel = objects[new_id]
    xdg_toplevel.set_callback("wm_capabilities")
    xdg_toplevel.set_callback("configure_bounds")
    xdg_toplevel.set_callback("configure")
    xdg_toplevel.set_callback("close", stop)

    # xdg_toplevel::set_title("WayGUI")
    write_request(
        xdg_toplevel, "set_title",
        title=WINDOW_TITLE
    )

    # wl_surface::commit()
    write_request(wl_surface, "commit")

    flush()

    # wl_shm::create_pool(new_id, fd=0, size=500x500x4x2)
    create_shared_memory()
    write_request(
        wl_shm, "create_pool",
        id=(new_id := len(objects)),
        fd=0,
        size=POOL_SIZE,
    )
    wl_shm_pool = objects[new_id]

    # wl_shm_pool::create_buffer(new_id, offset=0, width=500, height=500, stride=500*4, format=xrgb8888)
    write_request(
        wl_shm_pool, "create_buffer",
        id=(new_id := len(objects)),
        offset=0,
        width=WIDTH,
        height=HEIGHT,
        stride=STRIDE,
        format=1,  # xrgb8888
    )
    wl_buffer = objects[new_id]

    # wl_surface::attach(buffer=wl_buffer, x=0, y=0)
    write_request(
        wl_surface, "attach",
        buffer=wl_buffer.obj_id.value,
        x=0,
        y=0
    )

    # wl_surface::commit()
    write_request(wl_surface, "commit")

    # noinspection PyUnresolvedReferences,PyProtectedMember
    flush([shm._fd])

    while RUNNING:
        flush()

    sock.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        pool_data.close()
        shm.unlink()
        shm.close()
