import socket
import threading
import pytest

from reversi.net.tcp_game import TcpGame
from reversi.protocol import ERROR

def _socketpair_or_skip():
    if hasattr(socket, "socketpair"):
        return socket.socketpair()
    pytest.skip("socket.socketpair() not available")

def test_malformed_line_triggers_error_reply():
    s_recv, s_send = _socketpair_or_skip()
    recv = TcpGame.from_connected(s_recv, timeout=1.0)
    send = TcpGame.from_connected(s_send, timeout=1.0)

    def receiver():
        line = recv.recv_line()
        # Not PASS / MOVE / outcome / ERROR → send ERROR and close
        assert not line.startswith("MOVE:")
        recv.send_line(ERROR)
        recv.close()

    def sender():
        send.send_line("HELLO:WORLD")
        got = send.recv_line()
        assert got == ERROR
        send.close()

    tR = threading.Thread(target=receiver, daemon=True)
    tS = threading.Thread(target=sender, daemon=True)
    tR.start(); tS.start()
    tR.join(2); tS.join(2)
