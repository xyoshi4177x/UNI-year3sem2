import socket
import threading
import pytest

from reversi.net.tcp_game import TcpGame
from reversi.protocol import encode_move, decode_move, PASS
from reversi.game.board import Board, BLACK, WHITE
from reversi.game.rules import valid_moves, apply_move


def _socketpair_or_skip():
    if hasattr(socket, "socketpair"):
        return socket.socketpair()
    pytest.skip("socket.socketpair() not available on this platform/Python")


def test_two_peer_exchange_moves_keeps_boards_in_sync():
    """
    Simulates a short opening where P1(BLACK) and P2(WHITE) alternate legal moves.
    Asserts both peers end with identical board states.
    """
    s_p1, s_p2 = _socketpair_or_skip()
    p1 = TcpGame.from_connected(s_p1, timeout=2.0)
    p2 = TcpGame.from_connected(s_p2, timeout=2.0)

    # Both sides start from identical initial boards
    board_p1 = Board.initial()
    board_p2 = Board.initial()

    moves_to_play_each = 2  # small, fast opening

    def run_p1():
        nonlocal board_p1
        color_me, color_opp = BLACK, WHITE

        for _ in range(moves_to_play_each):
            # My turn: choose FIRST legal move deterministically
            mvs = valid_moves(board_p1, color_me)
            assert mvs, "BLACK should have a legal move in opening"
            r, c = mvs[0]
            board_p1 = apply_move(board_p1, color_me, r, c)
            p1.send_line(encode_move(r, c))

            # Opponent turn: receive and apply
            line = p1.recv_line()
            msg = decode_move(line)
            board_p1 = apply_move(board_p1, color_opp, msg.row, msg.col)

    def run_p2():
        nonlocal board_p2
        color_me, color_opp = WHITE, BLACK

        for _ in range(moves_to_play_each):
            # BLACK moves first — I should receive a move before I play
            line = p2.recv_line()
            msg = decode_move(line)
            board_p2 = apply_move(board_p2, color_opp, msg.row, msg.col)

            # Now my turn (WHITE)
            mvs = valid_moves(board_p2, color_me)
            assert mvs, "WHITE should have a legal reply in opening"
            r, c = mvs[0]
            board_p2 = apply_move(board_p2, color_me, r, c)
            p2.send_line(encode_move(r, c))

    t1 = threading.Thread(target=run_p1, daemon=True)
    t2 = threading.Thread(target=run_p2, daemon=True)
    try:
        t1.start(); t2.start()
        t1.join(timeout=5); t2.join(timeout=5)
        assert not t1.is_alive() and not t2.is_alive(), "Threads didn’t finish"

        # Assert both boards are identical after the exchange
        assert board_p1.grid == board_p2.grid

    finally:
        p1.close()
        p2.close()
