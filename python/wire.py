import os
import socket
from io import BytesIO

import wl_util as wl

interface = wl.build_interface()
objects = [
    None,
    wl.WLObject(wl.ObjID(1), "wl_display", interface["wl_display"])
]
registry = {
    "wl_display": 1
}


def build_request(wl_object: wl.WLObject, wl_request_name, **kwargs) -> bytes:
    request = wl_object.interface.requests[wl_request_name]
    header = wl.Header(wl_object.obj_id, request.opcode)
    args = []
    for arg in request.args:
        arg_obj = arg.type_(kwargs[arg.name])
        if arg.type_ == wl.NewID:
            new_id = kwargs[arg.name]
            new_obj = wl.WLObject(new_id, arg.new_interface, interface[arg.new_interface])
            objects.insert(new_id, new_obj)

        args.append(arg_obj)

    message = wl.Message(header, args)
    return message.serialize()


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
    wl_display = objects[registry["wl_display"]]
    data = build_request(wl_display, "get_registry", registry=len(objects))

    sock.send(data)
    response = sock.recv(4096)
    print(response)
    sock.close()


if __name__ == "__main__":
    main()
