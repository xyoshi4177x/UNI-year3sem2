import socket
import threading
import time
import pytest

from reversi.net.tcp_game import TcpGame
from reversi.game.board import Board, BLACK, WHITE
from reversi.game.outcome import outcome_token_for, verify_peer_outcome
from reversi.protocol import YOU_WIN, YOU_LOSE, DRAW, ERROR

def _socketpair_or_skip():
    if hasattr(socket, "socketpair"):
        return socket.socketpair()
    pytest.skip("socket.socketpair() not available")

def _full_board(b_count: int, w_count: int) -> Board:
    total = 64
    assert b_count + w_count == total
    rows = []
    left = b_count
    for _ in range(8):
        row = []
        for _ in range(8):
            if left > 0:
                row.append("B"); left -= 1
            else:
                row.append("W")
        rows.append(row)
    return Board.from_rows(rows)

def test_outcome_consistent_accept_and_close():
    s1, s2 = _socketpair_or_skip()
    p1 = TcpGame.from_connected(s1, timeout=1.0)  # P1 = BLACK (sender)
    p2 = TcpGame.from_connected(s2, timeout=1.0)  # P2 = WHITE (receiver)

    board = _full_board(38, 26)  # Black wins
    tok_p1 = outcome_token_for(board, BLACK)  # SHOULD be "YOU LOSE" (to White)

    def th_sender():
        p1.send_line(tok_p1)
        # give receiver time to read before closing to avoid rare race
        time.sleep(0.05)
        p1.close()

    recv_ok = {"ok": False}

    def th_receiver():
        line = p2.recv_line()
        assert line in (YOU_WIN, YOU_LOSE, DRAW)
        # Receiver is WHITE; token is addressed to WHITE
        assert verify_peer_outcome(board, WHITE, line) is True
        recv_ok["ok"] = True
        p2.close()

    t1 = threading.Thread(target=th_sender, daemon=True)
    t2 = threading.Thread(target=th_receiver, daemon=True)
    t1.start(); t2.start()
    t1.join(2); t2.join(2)
    assert recv_ok["ok"] is True

def test_outcome_mismatch_triggers_error_response():
    s1, s2 = _socketpair_or_skip()
    p1 = TcpGame.from_connected(s1, timeout=1.0)  # sender (peer)
    p2 = TcpGame.from_connected(s2, timeout=1.0)  # receiver verifying

    board = _full_board(40, 24)   # Black wins
    # LIE: sender (assume BLACK) says "YOU WIN" (telling WHITE they win) — inconsistent
    wrong_tok = YOU_WIN

    got_error = {"flag": False}

    def th_receiver():
        line = p2.recv_line()                  # receive bogus token (addressed to WHITE)
        assert verify_peer_outcome(board, WHITE, line) is False
        p2.send_line(ERROR)                    # reply with ERROR
        time.sleep(0.05)                       # allow sender to read before we close
        p2.close()

    def th_sender():
        p1.send_line(wrong_tok)
        # Expect to receive ERROR in response
        line = p1.recv_line()
        got_error["flag"] = (line == ERROR)
        p1.close()

    tR = threading.Thread(target=th_receiver, daemon=True)
    tS = threading.Thread(target=th_sender, daemon=True)
    tR.start(); tS.start()
    tR.join(2); tS.join(2)
    assert got_error["flag"] is True
