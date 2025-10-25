from reversi.game.board import Board, BLACK, WHITE
from reversi.game.outcome import outcome_token_for, verify_peer_outcome
from reversi.protocol import YOU_WIN, YOU_LOSE, DRAW

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

def test_outcome_token_for_peer_addressed():
    # BLACK 34 – WHITE 30 → Black is winning → send "YOU LOSE" to peer
    b = _full_board(34, 30)
    assert outcome_token_for(b, BLACK) == YOU_LOSE
    assert outcome_token_for(b, WHITE) == YOU_WIN

    # Draw
    d = _full_board(32, 32)
    assert outcome_token_for(d, BLACK) == DRAW
    assert outcome_token_for(d, WHITE) == DRAW

def test_verify_peer_outcome_consistency_and_mismatch():
    b = _full_board(40, 24)  # Black winning
    # If I am WHITE and receive "YOU LOSE", that means I (WHITE) am losing → consistent
    assert verify_peer_outcome(b, WHITE, YOU_LOSE) is True
    assert verify_peer_outcome(b, WHITE, YOU_WIN) is False
    # If I am BLACK and receive "YOU WIN", I am winning → consistent
    assert verify_peer_outcome(b, BLACK, YOU_WIN) is True
    assert verify_peer_outcome(b, BLACK, YOU_LOSE) is False
