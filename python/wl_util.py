import sys
import struct
from dataclasses import dataclass, field
from functools import partial
from io import BytesIO
from typing import Callable, Dict, Optional, Tuple
from xml.etree import ElementTree


def padding(size: int) -> int:
    return (4 - (size % 4)) % 4





@dataclass
class WLObject:
    obj_id: ObjID | int
    # indices in this list are used to match events to callbacks
    callbacks: Optional[Dict[int, Callable]] = field(default_factory=lambda: {})

    def __post_init__(self):
        if isinstance(self.obj_id, int):
            self.obj_id = ObjID(self.obj_id)

    def default_callback(self, event_name: str, **kwargs):
        print(f"{self.name}::{event_name} -> {kwargs}")

    def set_callback(self, event: str, func: Callable = None):
        if func is None:
            func = partial(self.default_callback, event)
        self.callbacks[self.interface.events[event].opcode] = func

    def __repr__(self):
        return f"WLObject({self.obj_id.value}, {self.name})"


@dataclass
class WLInterface:
    name: str
    version: int
    requests: Dict[Union[str, int], "WLFuncs"]
    events: Dict[Union[str, int], "WLFuncs"]


@dataclass
class WLFuncs:
    opcode: int
    name: str
    args: List["WLArgument"]
    type_: str = None


class WLRequest(WLFuncs):
    pass


class WLEvent(WLFuncs):
    pass


@dataclass
class WLArgument:
    name: str
    type_: type[WLPrimitive]
    new_interface: Optional[str] = None


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


def build_interface(path="/usr/share/wayland/wayland.xml"):
    xml = ElementTree.parse(path)

    interface = {}
    arg_map = {
        "int": Int32,
        "uint": UInt32,
        "fixed": "fixed",
        "object": ObjID,
        "new_id": NewID,
        "string": String,
        "fd": Fd,
        "array": Array,
    }

    for interface_tag in xml.getroot().iter("interface"):
        name = interface_tag.attrib["name"]
        interface_obj = WLInterface(
            name,
            int(interface_tag.attrib["version"]),
            {}, {}
        )

        for opcode, request_tag in enumerate(interface_tag.iter("request")):
            request_obj = WLRequest(
                opcode,
                (req_name := request_tag.attrib["name"]),
                [],
                type_=request_tag.attrib.get("type", None),
            )

            for arg_tag in request_tag.iter("arg"):
                # noinspection PyTypeChecker
                arg_obj = WLArgument(
                    arg_tag.attrib["name"],
                    arg_map[arg_tag.attrib["type"]],
                    arg_tag.attrib.get("interface", None)
                )

                if arg_obj.type_ == NewID and arg_obj.new_interface is None:
                    request_obj.args.append(WLArgument("new_interface_name", String))
                    request_obj.args.append(WLArgument("new_interface_version", UInt32))

                request_obj.args.append(arg_obj)

            interface_obj.requests[req_name] = request_obj
            interface_obj.requests[opcode] = request_obj

        for opcode, event_tag in enumerate(interface_tag.iter("event")):
            event_obj = WLEvent(
                opcode,
                (event_name := event_tag.attrib["name"]),
                [],
                type_=event_tag.attrib.get("type", None)
            )

            for arg_tag in event_tag.iter("arg"):
                # noinspection PyTypeChecker
                arg_obj = WLArgument(
                    arg_tag.attrib["name"],
                    arg_map[arg_tag.attrib["type"]],
                    arg_tag.attrib.get("interface", None)
                )

                event_obj.args.append(arg_obj)

            interface_obj.events[event_name] = event_obj
            interface_obj.events[opcode] = event_obj

        interface[name] = interface_obj

    return interface
