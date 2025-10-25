import socket
import threading
import pytest

from reversi.net.tcp_game import TcpGame
from reversi.protocol import encode_move, decode_move, PASS
from reversi.game.board import Board, BLACK, WHITE
from reversi.game.rules import valid_moves, apply_move, has_any_move


def _socketpair_or_skip():
    if hasattr(socket, "socketpair"):
        return socket.socketpair()
    pytest.skip("socket.socketpair() not available on this platform/Python")


def _board_where_black_must_pass() -> Board:
    """
    Create a board where BLACK has no legal moves but WHITE does.
    Construction:
      - Start with all WHITE.
      - Place a single BLACK at (3,3).
      - Make (4,4) EMPTY.
    WHITE playing at (4,4) flips (3,3) along the NW ray.
    """
    rows = [["W"] * 8 for _ in range(8)]
    rows[3][3] = "B"  # single black island
    rows[4][4] = "."  # the only empty; legal for WHITE, not for BLACK
    return Board.from_rows(rows)



def test_pass_flow_and_sync():
    """
    P1 is BLACK and has no moves → sends PASS.
    P2 (WHITE) receives PASS, makes a legal move.
    P1 receives that move. Boards stay identical.
    """
    s_p1, s_p2 = _socketpair_or_skip()
    p1 = TcpGame.from_connected(s_p1, timeout=2.0)
    p2 = TcpGame.from_connected(s_p2, timeout=2.0)

    board_p1 = _board_where_black_must_pass()
    board_p2 = Board.from_rows(board_p1.to_rows())  # clone

    assert not has_any_move(board_p1, BLACK)
    assert has_any_move(board_p1, WHITE)

    def run_p1():
        nonlocal board_p1
        # No BLACK move: send PASS
        p1.send_line(PASS)
        # Receive WHITE move and apply
        line = p1.recv_line()
        msg = decode_move(line)
        board_p1 = apply_move(board_p1, WHITE, msg.row, msg.col)

    def run_p2():
        nonlocal board_p2
        # Expect PASS from BLACK
        line = p2.recv_line()
        assert line == PASS
        # WHITE plays first legal move
        mvs = valid_moves(board_p2, WHITE)
        assert mvs, "WHITE should have a move"
        r, c = mvs[0]
        board_p2 = apply_move(board_p2, WHITE, r, c)
        p2.send_line(encode_move(r, c))

    t1 = threading.Thread(target=run_p1, daemon=True)
    t2 = threading.Thread(target=run_p2, daemon=True)
    try:
        t1.start(); t2.start()
        t1.join(timeout=5); t2.join(timeout=5)
        assert not t1.is_alive() and not t2.is_alive(), "Threads didn’t finish"
        assert board_p1.grid == board_p2.grid
    finally:
        p1.close()
        p2.close()
