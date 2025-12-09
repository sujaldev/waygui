import sys
import struct
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Optional


class WLPrimitive:
    """Base class for wayland primitive types."""
    pass

    def serialize(self) -> bytes:
        pass


@dataclass
class UInt32(WLPrimitive):
    value: int

    def serialize(self) -> bytes:
        return struct.pack("=I", self.value)


@dataclass
class Int32(WLPrimitive):
    value: int

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
    def frombytes(data: BytesIO) -> "String":
        length = data.read()
        return String()

    def serialize(self) -> bytes:
        value = bytes(self.value, "utf8")
        value += b"\0"  # NULL terminator

        size = len(value)
        padding = (32 - (size % 32)) % 32
        value += b"\0" * padding
        size += padding

        return struct.pack("=I", size) + value


@dataclass
class WLObject:
    obj_id: ObjID
    name: str
    interface: "WLInterface"


@dataclass
class WLInterface:
    name: str
    version: int
    requests: Dict[str, "WLFuncs"]
    events: List["WLFuncs"]


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
