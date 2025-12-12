import functools
import inspect
import struct
import sys
from dataclasses import dataclass, field
from functools import partial
from io import BytesIO
from typing import Callable, ClassVar, Dict, List, Optional, ParamSpec, Tuple, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from . import ConnectionManager

from .primitives import *

__all__ = [
    "WLObject", "request", "Header", "Message"
]

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class WLObject:
    obj_id: ObjID | int
    connection: "ConnectionManager"
    # indices in this list are used to match events to callbacks
    callbacks: Optional[Dict[str, Callable]] = field(default_factory=lambda: {})

    EVENTS: ClassVar[List[str]] = []

    def __post_init__(self):
        if isinstance(self.obj_id, int):
            self.obj_id = ObjID(self.obj_id)

    def default_callback(self, event_name: str, *args, **kwargs):
        print(f"{type(self).__name__}::{event_name} -> args: {args}, kwargs: {kwargs}")

    def set_callback(self, event: str, func: Callable = None):
        if func is None:
            func = partial(self.default_callback, event)
        self.callbacks[event] = partial(func, event)

    def serialize_request(self, opcode: int, *args: WLPrimitive):
        header = Header(self.obj_id, opcode)
        return Message(header, args).serialize()

    def __repr__(self):
        return f"{type(self).__name__}({self.obj_id.value})"


def request(func: Callable[P, R]) -> Callable[P, R]:
    # Decorator that converts arguments passed to a method from python types to wayland primitive types (WLPrimitive).

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs):
        args = list(args)
        signature = inspect.signature(func).parameters

        for i, (arg_name, arg_type) in enumerate(signature.items()):
            if arg_name == "self":
                continue

            wl_primitive_type, constructor_type = signature[arg_name].annotation.__args__

            if i < len(args) and not isinstance(args[i], wl_primitive_type):
                args[i] = wl_primitive_type(getattr(args[i], "value", args[i]))
            elif not isinstance((value := kwargs.get(arg_name, None)), wl_primitive_type):
                kwargs[arg_name] = wl_primitive_type(getattr(value, "value", value))

        ret = func(*args, **kwargs)
        self = args[0]
        # noinspection PyProtectedMember
        self.connection._send_buffer += ret
        return ret

    return wrapper


@dataclass
class Header:
    obj_id: ObjID
    opcode: int
    size: int = 0

    @staticmethod
    def frombytes(data: BytesIO) -> Optional["Header"]:
        data = data.read(8)

        if not data:
            return None

        if sys.byteorder == "little":
            obj_id, opcode, size = struct.unpack("<IHH", data)
        else:
            obj_id, size, opcode = struct.unpack(">IHH", data)

        return Header(ObjID(obj_id), opcode, size)

    def serialize(self) -> bytes:
        obj_id = self.obj_id.serialize()
        if sys.byteorder == "little":
            return obj_id + struct.pack("<HH", self.opcode, self.size)
        else:
            return struct.pack(">HH", self.size, self.opcode)


@dataclass
class Message:
    header: Header
    args: Tuple[WLPrimitive, ...]

    def serialize_payload(self) -> bytes:
        payload = bytes()
        for arg in self.args:
            payload += arg.serialize()

        return payload

    def serialize(self) -> bytes:
        payload = self.serialize_payload()
        self.header.size = 8 + len(payload)
        return self.header.serialize() + payload
