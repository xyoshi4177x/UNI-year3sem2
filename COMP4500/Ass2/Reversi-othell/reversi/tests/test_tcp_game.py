import socket
import sys
import pytest

from reversi.net.tcp_game import TcpGame
from reversi.errors import ProtocolError


def _maybe_socketpair():
    if hasattr(socket, "socketpair"):
        return socket.socketpair()
    pytest.skip("socket.socketpair not available on this platform/Python")


def test_send_recv_line_roundtrip():
    s1, s2 = _maybe_socketpair()
    try:
        a = TcpGame.from_connected(s1)
        b = TcpGame.from_connected(s2)
        a.send_line("hello")
        assert b.recv_line() == "hello"
        b.send_line("world")
        assert a.recv_line() == "world"
    finally:
        a.close()
        b.close()


def test_recv_accepts_crlf_and_coalesced_packets():
    s1, s2 = _maybe_socketpair()
    try:
        a = TcpGame.from_connected(s1)
        b = TcpGame.from_connected(s2)
        # Send two lines together, one with CRLF, one with LF
        b_raw = b"first\r\nsecond\n"
        s2.sendall(b_raw)
        assert a.recv_line() == "first"
        assert a.recv_line() == "second"
    finally:
        a.close()
        b.close()


def test_send_line_rejects_newlines():
    s1, s2 = _maybe_socketpair()
    try:
        a = TcpGame.from_connected(s1)
        with pytest.raises(ProtocolError):
            a.send_line("bad\nline")
    finally:
        a.close()
        s2.close()


def test_recv_timeout_raises(monkeypatch):
    s1, s2 = _maybe_socketpair()
    try:
        a = TcpGame.from_connected(s1, timeout=0.05)
        # Don't send anything from s2 → expect timeout
        with pytest.raises(ProtocolError):
            a.recv_line()
    finally:
        a.close()
        s2.close()
