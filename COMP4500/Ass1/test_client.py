import argparse
import asyncio
from common import protocol, codes

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
DEFAULT_STUDENT_ID = 1234567  # change to yours


def maybe_corrupt(frame: bytes, mode: str | None) -> bytes:
    """
    Corrupt the encoded frame in one of two ways:
      - 'payload': flip 1 bit in the first payload byte
      - 'crc': flip 1 bit in the last CRC byte
    """
    if not mode:
        return frame

    b = bytearray(frame)
    length = len(b)

    if mode == "payload":
        # 4 bytes length + header size
        payload_start = 4 + protocol.HEADER_STRUCT.size
        if payload_start < length - 4:
            b[payload_start] ^= 0x01  # flip one bit
        return bytes(b)

    if mode == "crc":
        # last byte of CRC
        b[-1] ^= 0x01
        return bytes(b)

    return frame


async def send_request(host, port, msg_type, payload_dict, corrupt: str | None):
    reader, writer = await asyncio.open_connection(host, port)

    payload = protocol.kv_encode(payload_dict)
    frame = protocol.encode_frame(msg_type=msg_type, req_id=1, payload=payload)
    frame = maybe_corrupt(frame, corrupt)

    writer.write(frame)
    await writer.drain()

    # Read response
    length_prefix = await reader.readexactly(4)
    (frame_len,) = protocol.struct.unpack("!I", length_prefix)
    frame_rest = await reader.readexactly(frame_len)
    rsp_frame = length_prefix + frame_rest

    header, payload_bytes = protocol.decode_frame(rsp_frame)
    data = protocol.kv_decode(payload_bytes)

    writer.close()
    await writer.wait_closed()
    return header, data


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--student", type=int, default=DEFAULT_STUDENT_ID)
    ap.add_argument(
        "--corrupt",
        choices=["payload", "crc"],
        help="Corrupt the outgoing request to demo app-layer error detection",
    )
    args = ap.parse_args()

    print("=== Function 1: GET_WEIGHT (Dreamium) ===")
    h, d = await send_request(args.host, args.port, codes.TYPE_GET_WEIGHT, {"name": "Dreamium"}, args.corrupt)
    print("header:", h, "data:", d)

    print("\n=== Function 2: GET_QUANTITY (Dreamium) ===")
    h, d = await send_request(
        args.host, args.port, codes.TYPE_GET_QUANTITY, {"name": "Dreamium", "student": str(args.student)}, args.corrupt
    )
    print("header:", h, "data:", d)

    print("\n=== Function 3: ADD_ELEMENT (Testium, 999.99) ===")
    h, d = await send_request(
        args.host, args.port, codes.TYPE_ADD_ELEMENT, {"name": "Testium", "weight": "999.99"}, args.corrupt
    )
    print("header:", h, "data:", d)

    print("\n=== Re-check GET_WEIGHT (Testium) ===")
    h, d = await send_request(args.host, args.port, codes.TYPE_GET_WEIGHT, {"name": "Testium"}, args.corrupt)
    print("header:", h, "data:", d)


if __name__ == "__main__":
    asyncio.run(main())
