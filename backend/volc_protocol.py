import io
import logging
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, List, Optional
import websockets

logger = logging.getLogger(__name__)

class MsgType(IntEnum):
    """Message type enumeration"""
    Invalid = 0
    FullClientRequest = 0b1
    AudioOnlyClient = 0b10
    FullServerResponse = 0b1001
    AudioOnlyServer = 0b1011
    FrontEndResultServer = 0b1100
    Error = 0b1111
    
    # Alias
    ServerACK = AudioOnlyServer

    def __str__(self) -> str:
        return self.name if self.name else f"MsgType({self.value})"


class MsgTypeFlagBits(IntEnum):
    """Message type flag bits"""
    NoSeq = 0  # Non-terminal packet with no sequence
    PositiveSeq = 0b1  # Non-terminal packet with sequence > 0
    LastNoSeq = 0b10  # Last packet with no sequence
    NegativeSeq = 0b11  # Last packet with sequence < 0
    WithEvent = 0b100  # Payload contains event number (int32)


class VersionBits(IntEnum):
    """Version bits"""
    Version1 = 1


class HeaderSizeBits(IntEnum):
    """Header size bits"""
    HeaderSize4 = 1


class SerializationBits(IntEnum):
    """Serialization method bits"""
    Raw = 0
    JSON = 0b1
    Thrift = 0b11
    Custom = 0b1111


class CompressionBits(IntEnum):
    """Compression method bits"""
    None_ = 0
    Gzip = 0b1
    Custom = 0b1111

@dataclass
class Message:
    """Message object"""

    version: VersionBits = VersionBits.Version1
    header_size: HeaderSizeBits = HeaderSizeBits.HeaderSize4
    type: MsgType = MsgType.Invalid
    flag: MsgTypeFlagBits = MsgTypeFlagBits.NoSeq
    serialization: SerializationBits = SerializationBits.JSON
    compression: CompressionBits = CompressionBits.None_

    sequence: int = 0
    error_code: int = 0
    payload: bytes = b""

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        """Create message object from bytes"""
        if len(data) < 4: # Header is 4 bytes
            raise ValueError(f"Data too short: expected at least 4 bytes, got {len(data)}")

        # Byte 0: Version (4) + Header Size (4)
        b0 = data[0]
        # Byte 1: Msg Type (4) + Flags (4)
        b1 = data[1]
        # Byte 2: Serialization (4) + Compression (4)
        b2 = data[2]
        # Byte 3: Reserved (8)
        
        msg_type = MsgType(b1 >> 4)
        flag = MsgTypeFlagBits(b1 & 0b00001111)
        
        msg = cls(type=msg_type, flag=flag)
        msg.unmarshal(data)
        return msg

    def marshal(self) -> bytes:
        """Serialize message to bytes"""
        buffer = io.BytesIO()

        # Write header (4 bytes)
        # Byte 0
        buffer.write(struct.pack("B", (self.version << 4) | self.header_size))
        # Byte 1
        buffer.write(struct.pack("B", (self.type << 4) | self.flag))
        # Byte 2
        buffer.write(struct.pack("B", (self.serialization << 4) | self.compression))
        # Byte 3 (Reserved)
        buffer.write(b"\x00")

        # Write other fields based on type/flag
        writers = self._get_writers()
        for writer in writers:
            writer(buffer)

        return buffer.getvalue()

    def unmarshal(self, data: bytes) -> None:
        """Deserialize message from bytes"""
        buffer = io.BytesIO(data)
        
        # Skip header (4 bytes) already parsed partially in from_bytes
        buffer.read(4)

        # Read other fields
        readers = self._get_readers()
        for reader in readers:
            reader(buffer)

        # Check for remaining data?
        # In this simplified implementation we just read what we expect.

    def _get_writers(self) -> List[Callable[[io.BytesIO], None]]:
        """Get list of writer functions"""
        writers = []

        if self.type in [
            MsgType.FullClientRequest,
            MsgType.FullServerResponse,
            MsgType.FrontEndResultServer,
            MsgType.AudioOnlyClient,
            MsgType.AudioOnlyServer,
        ]:
            if self.flag in [MsgTypeFlagBits.PositiveSeq, MsgTypeFlagBits.NegativeSeq]:
                writers.append(self._write_sequence)
        elif self.type == MsgType.Error:
            writers.append(self._write_error_code)

        writers.append(self._write_payload)
        return writers

    def _get_readers(self) -> List[Callable[[io.BytesIO], None]]:
        """Get list of reader functions"""
        readers = []

        if self.type in [
            MsgType.FullClientRequest,
            MsgType.FullServerResponse,
            MsgType.FrontEndResultServer,
            MsgType.AudioOnlyClient,
            MsgType.AudioOnlyServer,
        ]:
            if self.flag in [MsgTypeFlagBits.PositiveSeq, MsgTypeFlagBits.NegativeSeq]:
                readers.append(self._read_sequence)
        elif self.type == MsgType.Error:
            readers.append(self._read_error_code)

        readers.append(self._read_payload)
        return readers

    def _write_sequence(self, buffer: io.BytesIO) -> None:
        buffer.write(struct.pack(">i", self.sequence))

    def _write_error_code(self, buffer: io.BytesIO) -> None:
        buffer.write(struct.pack(">I", self.error_code))

    def _write_payload(self, buffer: io.BytesIO) -> None:
        size = len(self.payload)
        buffer.write(struct.pack(">I", size))
        buffer.write(self.payload)

    def _read_sequence(self, buffer: io.BytesIO) -> None:
        self.sequence = struct.unpack(">i", buffer.read(4))[0]

    def _read_error_code(self, buffer: io.BytesIO) -> None:
        self.error_code = struct.unpack(">I", buffer.read(4))[0]

    def _read_payload(self, buffer: io.BytesIO) -> None:
        size_bytes = buffer.read(4)
        if size_bytes:
            size = struct.unpack(">I", size_bytes)[0]
            if size > 0:
                self.payload = buffer.read(size)


async def receive_message(websocket: websockets.WebSocketClientProtocol) -> Message:
    data = await websocket.recv()
    if isinstance(data, bytes):
        return Message.from_bytes(data)
    raise ValueError(f"Unexpected message type: {type(data)}")

async def full_client_request(websocket: websockets.WebSocketClientProtocol, payload: bytes) -> None:
    msg = Message(type=MsgType.FullClientRequest, flag=MsgTypeFlagBits.NoSeq)
    msg.payload = payload
    await websocket.send(msg.marshal())
