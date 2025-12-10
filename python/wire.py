import os
import socket
from io import BytesIO
from typing import Dict, Optional

import wl_util as wl

sock: Optional[socket.socket] = None
send_buffer = bytes()
recv_buffer = BytesIO()

interface = wl.build_interface()
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

    if name is None:
        name = os.getenv("WAYLAND_DISPLAY", default="wayland-0")

    if not name.startswith("/"):
        xdg_runtime_dir = os.getenv("XDG_RUNTIME_DIR", default=f"/run/user/{os.getuid()}")
        name = f"{xdg_runtime_dir}/{name}"

    sock.connect(name)


def flush():
    global send_buffer
    global recv_buffer

    if send_buffer:
        sock.send(send_buffer)
        del send_buffer
        send_buffer = bytes()

    data = sock.recv(4096)
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
    obj = objects[header.obj_id.value]
    kwarg_list = {}
    for arg in obj.interface.events[header.opcode].args:
        kwarg_list[arg.name] = arg.type_.frombytes(recv_buffer)
    obj.callbacks[header.opcode](**kwarg_list)


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


def main():
    global recv_buffer

    setup_socket()
    wl_display = objects[1]
    wl_display.callbacks[wl_display.interface.events["error"].opcode] = wl_display_error
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
    print(wl_compositor)

    flush()

    sock.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
