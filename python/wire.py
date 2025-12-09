import os
import socket
from io import BytesIO
from typing import Optional

import wl_util as wl

sock: Optional[socket.socket] = None
send_buffer = bytes()
recv_buffer = BytesIO()

interface = wl.build_interface()
objects = [
    None,
    wl.WLObject(wl.ObjID(1), "wl_display", interface["wl_display"])
]


def write_request(wl_object: wl.WLObject, wl_request_name, **kwargs):
    global send_buffer

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
    global sock
    global send_buffer

    if send_buffer:
        sock.send(send_buffer)
        send_buffer = bytes()


def parse_response():
    global recv_buffer

    header = wl.Header.frombytes(recv_buffer)
    obj = objects[header.obj_id.value]
    print(header)
    for arg in obj.interface.events[header.opcode].args:
        print(arg.type_.frombytes(recv_buffer))
    print("\n")


def event_loop():
    global recv_buffer

    setup_socket()
    wl_display = objects[1]
    write_request(wl_display, "get_registry", registry=len(objects))

    while True:
        flush()

        data = sock.recv(4096)
        data_len = len(data)
        if data_len == 0:
            break

        recv_buffer.write(data)
        recv_buffer.seek(-data_len, 1)

        while recv_buffer.tell() < data_len:
            parse_response()

        del recv_buffer
        recv_buffer = BytesIO()

    sock.close()


if __name__ == "__main__":
    try:
        event_loop()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(e)
    finally:
        sock.close()
