import pytest

from reversi.game.board import Board, BLACK, WHITE, EMPTY
from reversi.game.rules import valid_moves, apply_move, has_any_move, is_game_over, score
from reversi.errors import IllegalMoveError


def test_initial_valid_moves_black_and_white():
    b = Board.initial()
    mv_b = valid_moves(b, BLACK)
    mv_w = valid_moves(b, WHITE)
    # Exact sets depend on coordinate system; canonical openings are 4 each.
    assert len(mv_b) == 4
    assert len(mv_w) == 4
    # They should not be identical but symmetric
    assert set(mv_b) != set(mv_w)


def test_apply_move_flips_correctly():
    b = Board.initial()
    # One common opening is BLACK at (2,3) (row=2, col=3)
    b2 = apply_move(b, BLACK, 2, 3)
    # The placed stone exists
    assert b2.cell(2, 3) == BLACK
    # It should flip exactly one WHITE at (3,3)
    assert b.cell(3, 3) == WHITE
    assert b2.cell(3, 3) == BLACK
    # Other unrelated cells unchanged
    assert b2.cell(4, 4) == WHITE
    assert b2.cell(3, 4) == BLACK
    assert b2.cell(4, 3) == BLACK


def test_illegal_move_raises():
    b = Board.initial()
    with pytest.raises(IllegalMoveError):
        apply_move(b, BLACK, 0, 0)  # Not bracketed anywhere


def test_pass_detection_and_game_over_progression():
    # Construct a nearly full board with a forced pass sequence.
    # We'll create a board with only one EMPTY where only BLACK can move.
    rows = [[BLACK]*8 for _ in range(8)]
    # Put a small WHITE island and an EMPTY near it to allow exactly one BLACK move
    rows[3][3] = WHITE
    rows[3][4] = WHITE
    rows[4][3] = WHITE
    rows[4][4] = EMPTY
    b = Board.from_rows(rows)

    # BLACK should have at least one move; WHITE should have none after that move
    assert has_any_move(b, BLACK)
    # Apply the only BLACK move that flips at (4,4)
    # Find it programmatically so the test is robust:
    mvs = valid_moves(b, BLACK)
    assert mvs, "Expected at least one move for BLACK"
    b2 = apply_move(b, BLACK, *mvs[0])

    # Now check WHITE moves
    assert not has_any_move(b2, WHITE)

    # Game could be over if BLACK also has no moves (or board full)
    over = is_game_over(b2)
    assert over or has_any_move(b2, BLACK)  # Either over, or BLACK still can move


def test_score_counts_match_manual():
    b = Board.initial()
    # Initial: 2 black, 2 white
    assert score(b) == (2, 2)
    # After BLACK move (2,3), counts should be 4 black vs 1 white
    b2 = apply_move(b, BLACK, 2, 3)
    assert score(b2) == (4, 1)
