import sys
import struct
from dataclasses import dataclass, field
from io import BytesIO
from typing import Callable, Dict, List, Optional, Union
from xml.etree import ElementTree


class WLPrimitive:
    """Base class for wayland primitive types."""
    pass

    @staticmethod
    def frombytes(data: BytesIO) -> "WLPrimitive":
        pass

    def serialize(self) -> bytes:
        pass


@dataclass
class UInt32(WLPrimitive):
    value: int

    @staticmethod
    def frombytes(data: BytesIO) -> "UInt32":
        return UInt32(struct.unpack("=I", data.read(4))[0])

    def serialize(self) -> bytes:
        return struct.pack("=I", self.value)


@dataclass
class Int32(WLPrimitive):
    value: int

    @staticmethod
    def frombytes(data: BytesIO) -> "Int32":
        return Int32(struct.unpack("=i", data.read(4))[0])

    def serialize(self) -> bytes:
        return struct.pack("=i", self.value)


@dataclass
class ObjID(UInt32):
    pass


@dataclass
class NewID(UInt32):
    pass


@dataclass
class String(WLPrimitive):
    value: str

    @staticmethod
    def padding(size: int) -> int:
        return (4 - (size % 4)) % 4

    @staticmethod
    def frombytes(data: BytesIO) -> "String":
        length = UInt32.frombytes(data).value
        value = data.read(length - 1)
        data.read(1 + String.padding(length))  # discard padding (if any exists)
        return String(value.decode("utf8"))

    def serialize(self) -> bytes:
        value = bytes(self.value, "utf8")
        value += b"\0"  # NULL terminator

        size = len(value)
        padding = String.padding(size)
        value += b"\0" * padding
        size += padding

        return struct.pack("=I", size) + value


@dataclass
class WLObject:
    obj_id: ObjID
    name: str
    interface: "WLInterface"
    # indices in this list are used to match events to callbacks
    callbacks: Optional[Dict[int, Callable]] = field(default_factory=lambda: {})

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
    type_: WLPrimitive
    new_interface: Optional[str]


@dataclass
class Header:
    obj_id: ObjID
    opcode: int
    size: int = 0

    @staticmethod
    def frombytes(data: BytesIO) -> "Header":
        data = data.read(8)
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
    args: list[WLPrimitive]

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
        "fd": "fd",
        "array": "array",
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
