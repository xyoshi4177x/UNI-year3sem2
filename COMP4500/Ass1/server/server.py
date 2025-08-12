# server/server.py
import argparse
import asyncio
from decimal import Decimal
from typing import Dict

from common import protocol, codes
from server.storage import ElementStore


def kv_ok(data: Dict[str, str], req_id: int) -> bytes:
    payload = protocol.kv_encode(data)
    return protocol.encode_frame(
        msg_type=codes.TYPE_RESPONSE, req_id=req_id, payload=payload, flags=0
    )


def kv_err(code: int, msg: str, req_id: int) -> bytes:
    payload = protocol.kv_encode({"code": str(code), "msg": msg})
    return protocol.encode_frame(
        msg_type=codes.TYPE_RESPONSE, req_id=req_id, payload=payload, flags=codes.FLAG_ERROR
    )


class ElementServer:
    def __init__(self, store: ElementStore):
        self.store = store

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        try:
            while True:
                # Read 4-byte length prefix
                length_prefix = await reader.readexactly(4)
                # Now read the rest of the frame
                (frame_len,) = protocol.struct.unpack("!I", length_prefix)
                frame_rest = await reader.readexactly(frame_len)
                frame = length_prefix + frame_rest

                try:
                    header, payload = protocol.decode_frame(frame)
                except ValueError as e:
                    # Bad CRC or malformed frame
                    # We don’t know req_id safely here; echo 0
                    writer.write(kv_err(codes.ERR_BAD_CRC, str(e), req_id=0))
                    await writer.drain()
                    continue

                # Version check
                if header["version"] != codes.PROTOCOL_VERSION:
                    writer.write(kv_err(codes.ERR_BAD_VERSION, "Unsupported protocol version", header["req_id"]))
                    await writer.drain()
                    continue

                # Decode payload KV
                try:
                    kv = protocol.kv_decode(payload)
                except Exception:
                    writer.write(kv_err(codes.ERR_MALFORMED_PAYLOAD, "Malformed payload", header["req_id"]))
                    await writer.drain()
                    continue

                msg_type = header["type"]

                if msg_type == codes.TYPE_GET_WEIGHT:
                    await self._handle_get_weight(kv, header["req_id"], writer)
                elif msg_type == codes.TYPE_GET_QUANTITY:
                    await self._handle_get_quantity(kv, header["req_id"], writer)
                elif msg_type == codes.TYPE_ADD_ELEMENT:
                    await self._handle_add(kv, header["req_id"], writer)
                else:
                    writer.write(kv_err(codes.ERR_BAD_TYPE, f"Unknown type {msg_type}", header["req_id"]))
                    await writer.drain()
        except asyncio.IncompleteReadError:
            # client closed connection
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_get_weight(self, kv: Dict[str, str], req_id: int, writer):
        name = kv.get("name", "").strip()
        if not name:
            writer.write(kv_err(codes.ERR_MISSING_FIELD, "name required", req_id))
            await writer.drain()
            return
        try:
            weight: Decimal = self.store.get_weight(name)
        except KeyError:
            writer.write(kv_err(codes.ERR_NOT_FOUND, f"{name} not found", req_id))
            await writer.drain()
            return
        writer.write(kv_ok({"weight": str(weight.normalize())}, req_id))
        await writer.drain()

    async def _handle_get_quantity(self, kv: Dict[str, str], req_id: int, writer):
        name = kv.get("name", "").strip()
        student = kv.get("student", "").strip()
        if not name or not student.isdigit():
            writer.write(kv_err(codes.ERR_MISSING_FIELD, "name and numeric student required", req_id))
            await writer.drain()
            return
        try:
            qty = self.store.get_quantity(name, int(student))
        except KeyError:
            writer.write(kv_err(codes.ERR_NOT_FOUND, f"{name} not found", req_id))
            await writer.drain()
            return
        writer.write(kv_ok({"quantity": str(qty)}, req_id))
        await writer.drain()

    async def _handle_add(self, kv: Dict[str, str], req_id: int, writer):
        name = kv.get("name", "").strip()
        weight = kv.get("weight", "").strip()
        if not name or not weight:
            writer.write(kv_err(codes.ERR_MISSING_FIELD, "name and weight required", req_id))
            await writer.drain()
            return
        # Very light name validation
        if len(name) > 60:
            writer.write(kv_err(codes.ERR_INVALID_NAME, "name too long", req_id))
            await writer.drain()
            return
        try:
            self.store.add_element(name, weight)  # weight stays string → Decimal inside
        except ValueError as e:
            msg = str(e)
            if "Duplicate" in msg:
                writer.write(kv_err(codes.ERR_DUPLICATE, msg, req_id))
            else:
                writer.write(kv_err(codes.ERR_INVALID_WEIGHT, "invalid weight", req_id))
            await writer.drain()
            return
        writer.write(kv_ok({"status": "ok"}, req_id))
        await writer.drain()


async def main():
    parser = argparse.ArgumentParser(description="Atomic Element Server")
    parser.add_argument("--port", type=int, default=5000, help="TCP port to listen on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind address")
    parser.add_argument("--elements", type=str, default="data/ass1_base_data.csv", help="CSV path")
    args = parser.parse_args()

    store = ElementStore()
    store.load_from_csv(args.elements)

    server = ElementServer(store)
    srv = await asyncio.start_server(server.handle_client, host=args.host, port=args.port)
    sockets = ", ".join(str(sock.getsockname()) for sock in srv.sockets or [])
    print(f"Server listening on {sockets}")

    async with srv:
        await srv.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
