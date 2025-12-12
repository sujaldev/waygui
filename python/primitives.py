import struct
from dataclasses import dataclass
from io import BytesIO

__all__ = [
    "WLPrimitive", "UInt32", "Int32", "ObjID", "NewID", "String", "Fd", "Array", "Fixed"
]


def padding(size: int) -> int:
    return (4 - (size % 4)) % 4


@dataclass
class WLPrimitive:
    """Base class for wayland primitive types."""

    def __init__(self, *args, **kwargs):
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
    def frombytes(data: BytesIO) -> "String":
        length = UInt32.frombytes(data).value
        value = data.read(length - 1)
        data.read(1 + padding(length))  # discard padding (if any exists)
        return String(value.decode("utf8"))

    def serialize(self) -> bytes:
        value = bytes(self.value, "utf8")
        value += b"\0"  # NULL terminator

        size = len(value)
        value += b"\0" * padding(size)

        return struct.pack("=I", size) + value


class Fd(UInt32):
    """
    The file descriptor is not stored in the message buffer,
    but in the ancillary data of the UNIX domain socket message (msg_control).
    """
    value = 0  # Does not matter what value we store here, this class is just to declare a fd type.

    def serialize(self) -> bytes:
        # The file descriptor is sent via ancillary data,
        # it does not serialize to actual bytes in the wire format.
        return b""


@dataclass
class Array(WLPrimitive):
    """
    Starts with 32-bit array size in bytes,
    followed by the array contents verbatim,
    and finally padding to a 32-bit boundary.
    """
    size: int
    data: bytes

    @staticmethod
    def frombytes(data: BytesIO) -> "WLPrimitive":
        size = UInt32.frombytes(data).value
        array = data.read(size)
        data.read(padding(size))  # discard padding (if any exists)
        return Array(size, array)

    def serialize(self) -> bytes:
        data = UInt32(self.size).serialize() + self.data
        data += b"\0" * padding(len(data))
        return data


@dataclass
class Fixed(WLPrimitive):
    """
    Signed 24.8 decimal numbers. It is a signed decimal type
    which offers a sign bit, 23 bits of integer precision and
    8 bits of decimal precision. This is exposed as an opaque
    struct with conversion helpers to and from double and int
    on the C API side.
    """
    value: float

    @staticmethod
    def frombytes(data: BytesIO) -> "WLPrimitive":
        raise NotImplementedError

    def serialize(self) -> bytes:
        raise NotImplementedError
