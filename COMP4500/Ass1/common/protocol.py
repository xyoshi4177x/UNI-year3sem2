# common/protocol.py
import struct
import zlib
from typing import Dict, Tuple
from common import codes

"""
Frame format:
[4 bytes length][8 bytes header][payload bytes][4 bytes CRC32]
Length = total frame size (header + payload + CRC)
Header = ver(1), type(1), flags(1), fmt(1), req_id(2), reserved(2)
"""

HEADER_STRUCT = struct.Struct("!BBBBHH")  # network byte order


def kv_encode(data: Dict[str, str]) -> bytes:
    """Encode dict to key=value lines (UTF-8)."""
    return "\n".join(f"{k}={v}" for k, v in data.items()).encode("utf-8")


def kv_decode(data: bytes) -> Dict[str, str]:
    """Decode key=value lines (UTF-8) to dict."""
    lines = data.decode("utf-8").splitlines()
    result = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def encode_frame(
    msg_type: int,
    req_id: int,
    payload: bytes,
    flags: int = 0,
    fmt: int = 0,
    version: int = codes.PROTOCOL_VERSION,
) -> bytes:
    """Build a complete frame with header, payload, and CRC."""
    header = HEADER_STRUCT.pack(version, msg_type, flags, fmt, req_id, 0)
    crc = zlib.crc32(header + payload) & 0xFFFFFFFF
    frame_len = HEADER_STRUCT.size + len(payload) + 4  # header + payload + CRC
    return struct.pack("!I", frame_len) + header + payload + struct.pack("!I", crc)


def decode_frame(data: bytes) -> Tuple[dict, bytes]:
    """Decode a complete frame into header dict and payload."""
    if len(data) < 4:
        raise ValueError("Incomplete frame length")

    (frame_len,) = struct.unpack("!I", data[:4])
    if len(data) != frame_len + 4:
        raise ValueError("Frame length mismatch")

    header_bytes = data[4 : 4 + HEADER_STRUCT.size]
    payload_bytes = data[4 + HEADER_STRUCT.size : -4]
    (crc_recv,) = struct.unpack("!I", data[-4:])

    crc_calc = zlib.crc32(header_bytes + payload_bytes) & 0xFFFFFFFF
    if crc_calc != crc_recv:
        raise ValueError(f"CRC mismatch: got {crc_recv}, expected {crc_calc}")

    ver, msg_type, flags, fmt, req_id, _ = HEADER_STRUCT.unpack(header_bytes)
    header_dict = {
        "version": ver,
        "type": msg_type,
        "flags": flags,
        "fmt": fmt,
        "req_id": req_id,
    }

    return header_dict, payload_bytes
