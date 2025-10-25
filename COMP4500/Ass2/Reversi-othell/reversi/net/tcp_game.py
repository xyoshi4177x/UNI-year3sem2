# reversi/net/tcp_game.py
# Zachary Chan c3468750
from __future__ import annotations

import socket
from typing import Tuple, Optional

from ..errors import ProtocolError


_DEFAULT_TIMEOUT = 5.0          # seconds per socket op
_MAX_LINE_LEN = 1024            # guardrail against absurdly long lines
_EOL = b"\n"                    # we send \n; we accept \n or \r\n


class TcpGame:
    """
    Small, line-oriented TCP wrapper:
      - UTF-8 text protocol
      - send_line(): str -> '\n'-terminated
      - recv_line(): returns a single line (without trailing CR/LF)
      - raises ProtocolError on timeout/disconnect/malformed
    """

    def __init__(self, sock: socket.socket, timeout: float = _DEFAULT_TIMEOUT):
        self._sock = sock
        self._sock.settimeout(timeout)
        self._rbuf = bytearray()

    @classmethod
    def from_connected(cls, sock: socket.socket, timeout: float = _DEFAULT_TIMEOUT) -> "TcpGame":
        """
        Wrap an already-connected socket.
        """
        return cls(sock, timeout=timeout)

    @property
    def peername(self) -> Tuple[str, int]:
        try:
            return self._sock.getpeername()
        except OSError:
            return ("<closed>", 0)

    def set_timeout(self, seconds: float) -> None:
        self._sock.settimeout(seconds)

    def send_line(self, line: str) -> None:
        """
        Send a single logical line (appends '\n').
        """
        if "\n" in line or "\r" in line:
            # Keep wire format single-line and simple
            raise ProtocolError("send_line cannot contain CR/LF")
        data = (line + "\n").encode("utf-8", errors="strict")
        try:
            self._sock.sendall(data)
        except (socket.timeout, OSError) as e:
            raise ProtocolError(f"send_line failed: {e}") from e

    def recv_line(self) -> str:
        """
        Receive a single logical line, returning it without trailing CR/LF.
        Raises ProtocolError on timeout, disconnect, or overly long line.
        """
        while True:
            # Do we already have a full line?
            nl = self._rbuf.find(ord("\n"))
            if nl != -1:
                raw = bytes(self._rbuf[:nl + 1])
                del self._rbuf[:nl + 1]
                # Strip one trailing LF and optional preceding CR
                if raw.endswith(b"\r\n"):
                    raw = raw[:-2]
                elif raw.endswith(b"\n"):
                    raw = raw[:-1]
                return raw.decode("utf-8", errors="strict")

            if len(self._rbuf) >= _MAX_LINE_LEN:
                raise ProtocolError("Incoming line exceeds max length")

            # Read more
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout as e:
                raise ProtocolError("recv_line timeout") from e
            except OSError as e:
                raise ProtocolError(f"recv_line failed: {e}") from e

            if not chunk:
                # Peer closed while we were waiting for a newline
                raise ProtocolError("Connection closed by peer")

            self._rbuf.extend(chunk)

    def close(self) -> None:
        try:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        finally:
            try:
                self._sock.close()
            except OSError:
                pass
