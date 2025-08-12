# client/client.py
import argparse
import asyncio
from decimal import Decimal, InvalidOperation
from typing import Dict

from common import protocol, codes


class Client:
    def __init__(self, host: str, port: int, student: int | None, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.student = student
        self.timeout = timeout
        self._next_req_id = 1

    def _req_id(self) -> int:
        rid = self._next_req_id
        self._next_req_id = (self._next_req_id % 65535) + 1
        return rid

    async def _send(self, msg_type: int, payload: Dict[str, str]) -> tuple[dict, Dict[str, str]]:
        """Send one request and return (header, kv_data). Raises on transport errors."""
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=self.timeout
        )
        try:
            frame = protocol.encode_frame(
                msg_type=msg_type,
                req_id=self._req_id(),
                payload=protocol.kv_encode(payload),
            )
            writer.write(frame)
            await writer.drain()

            # Read response frame (length + rest)
            length_prefix = await asyncio.wait_for(reader.readexactly(4), timeout=self.timeout)
            (frame_len,) = protocol.struct.unpack("!I", length_prefix)
            frame_rest = await asyncio.wait_for(reader.readexactly(frame_len), timeout=self.timeout)
            rsp = length_prefix + frame_rest

            header, payload_bytes = protocol.decode_frame(rsp)
            data = protocol.kv_decode(payload_bytes)
            return header, data
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    # ---- High-level operations ----
    async def get_weight(self, name: str):
        header, data = await self._send(codes.TYPE_GET_WEIGHT, {"name": name})
        self._print_response(header, data)

    async def get_quantity(self, name: str, student: int):
        header, data = await self._send(
            codes.TYPE_GET_QUANTITY, {"name": name, "student": str(student)}
        )
        self._print_response(header, data)

    async def add_element(self, name: str, weight: str):
        header, data = await self._send(codes.TYPE_ADD_ELEMENT, {"name": name, "weight": weight})
        self._print_response(header, data)

    # ---- UI helpers ----
    @staticmethod
    def _print_response(header: dict, data: Dict[str, str]):
        if header.get("flags", 0) & codes.FLAG_ERROR:
            code = data.get("code", "?")
            msg = data.get("msg", "Unknown error")
            print(f"❌ Error [{code}]: {msg}")
        else:
            # Print key=value on one line
            print("✅", ", ".join(f"{k}={v}" for k, v in data.items()))

    # ---- Input validation ----
    @staticmethod
    def _read_name(prompt: str) -> str:
        while True:
            name = input(prompt).strip()
            if name:
                return name
            print("Name cannot be empty.")

    @staticmethod
    def _read_weight(prompt: str) -> str:
        while True:
            raw = input(prompt).strip()
            try:
                w = Decimal(raw)
                if w > 0:
                    # return normalized string without float artifacts
                    return str(w.normalize())
            except (InvalidOperation, ValueError):
                pass
            print("Enter a positive number (e.g., 412.32).")

    @staticmethod
    def _read_student(default: int | None) -> int:
        if default is not None:
            return default
        while True:
            raw = input("Student number: ").strip()
            if raw.isdigit() and int(raw) > 0:
                return int(raw)
            print("Enter a positive integer student number.")

    async def run_menu(self):
        while True:
            print(
                "\n--- Atomic Client ---\n"
                "1) Get weight\n"
                "2) Get quantity\n"
                "3) Add element\n"
                "0) Quit"
            )
            choice = input("Select: ").strip()
            try:
                if choice == "1":
                    name = self._read_name("Element name: ")
                    await self.get_weight(name)
                elif choice == "2":
                    name = self._read_name("Element name: ")
                    sid = self._read_student(self.student)
                    await self.get_quantity(name, sid)
                elif choice == "3":
                    name = self._read_name("New element name: ")
                    weight = self._read_weight("New element weight: ")
                    await self.add_element(name, weight)
                elif choice == "0":
                    print("Bye.")
                    return
                else:
                    print("Invalid selection.")
            except (asyncio.TimeoutError, ConnectionError) as e:
                print(f"❌ Network error: {e}")
            except Exception as e:
                print(f"❌ Unexpected error: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Atomic Element Client")
    parser.add_argument("--host", default="127.0.0.1", help="Server hostname")
    parser.add_argument("--port", type=int, default=5000, help="Server TCP port")
    parser.add_argument("--student", type=int, help="Default student number")
    parser.add_argument("--timeout", type=float, default=5.0, help="Network timeout seconds")
    args = parser.parse_args()

    client = Client(args.host, args.port, args.student, args.timeout)
    await client.run_menu()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
