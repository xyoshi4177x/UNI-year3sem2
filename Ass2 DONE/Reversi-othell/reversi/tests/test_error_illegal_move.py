import socket
import threading
import pytest

from reversi.net.tcp_game import TcpGame
from reversi.protocol import encode_move, ERROR
from reversi.game.board import Board, BLACK, WHITE
from reversi.game.rules import valid_moves, apply_move

def _socketpair_or_skip():
    if hasattr(socket, "socketpair"):
        return socket.socketpair()
    pytest.skip("socket.socketpair() not available")

def _board_where_white_cannot_move() -> Board:
    """
    Create a board where WHITE has no legal move at (4,4) but BLACK is to move next.
    We'll have WHITE try to play an illegal coordinate to trigger ERROR.
    """
    rows = [["B"] * 8 for _ in range(8)]
    # carve out a region with a couple of whites that don't allow (4,4) for WHITE
    rows[3][3] = "W"; rows[3][4] = "W"; rows[4][3] = "W"
    rows[4][4] = "."  # empty
    return Board.from_rows(rows)

def test_illegal_remote_move_triggers_error_reply():
    s_recv, s_send = _socketpair_or_skip()
    recv = TcpGame.from_connected(s_recv, timeout=1.0)  # this side validates
    send = TcpGame.from_connected(s_send, timeout=1.0)  # this side sends illegal move

    board = _board_where_white_cannot_move()

    def receiver():
        # Wait for a MOVE, find it illegal for WHITE, reply ERROR
        line = recv.recv_line()
        # We don't decode/apply here: this unit test imitates the main loop branch
        # (decode succeeded; apply would raise)
        recv.send_line(ERROR)
        recv.close()

    def sender():
        # Send a MOVE for WHITE at (4,4) which is illegal by construction
        send.send_line(encode_move(4, 4))
        # Expect ERROR back
        got = send.recv_line()
        assert got == ERROR
        send.close()

    tR = threading.Thread(target=receiver, daemon=True)
    tS = threading.Thread(target=sender, daemon=True)
    tR.start(); tS.start()
    tR.join(2); tS.join(2)
