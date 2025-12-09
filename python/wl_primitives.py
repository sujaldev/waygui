import sys
import struct
from dataclasses import dataclass
from io import BytesIO


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
class Header:
    obj_id: int
    opcode: int
    size: int = 0

    @staticmethod
    def frombytes(data: BytesIO) -> "Header":
        data = data.read(8)
        if sys.byteorder == "little":
            obj_id, opcode, size = struct.unpack("<IHH", data)
        else:
            obj_id, size, opcode = struct.unpack(">IHH", data)

        return Header(obj_id, opcode, size)

    def serialize(self) -> bytes:
        if sys.byteorder == "little":
            return struct.pack("<IHH", self.obj_id, self.opcode, self.size)
        else:
            return struct.pack(">IHH", self.obj_id, self.size, self.opcode)


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
