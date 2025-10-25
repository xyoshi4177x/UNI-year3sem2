# reversi/game/rules.py
# Zachary Chan c3468750
from __future__ import annotations
from typing import Iterable, List, Optional, Sequence, Tuple
from .board import (
    Board,
    BLACK,
    WHITE,
    EMPTY,
    SIZE,
    in_bounds,
    opponent,
)
from ..errors import IllegalMoveError

# Directions: N, NE, E, SE, S, SW, W, NW
DIRS: Tuple[Tuple[int, int], ...] = (
    (-1, 0), (-1, 1), (0, 1), (1, 1),
    (1, 0), (1, -1), (0, -1), (-1, -1),
)


def _line_flips(board: Board, player: str, r: int, c: int, dr: int, dc: int) -> List[Tuple[int, int]]:
    """
    If placing at (r,c) brackets opponent stones along (dr,dc),
    return list of coordinates to flip along that ray; else [].
    """
    flips: List[Tuple[int, int]] = []
    rr, cc = r + dr, c + dc
    opp = opponent(player)

    if not in_bounds(rr, cc) or board.cell(rr, cc) != opp:
        return []  # immediate neighbor must be opponent

    # Collect opponent stones until we see our own stone
    while in_bounds(rr, cc):
        cell = board.cell(rr, cc)
        if cell == opp:
            flips.append((rr, cc))
        elif cell == player:
            return flips  # bracketed successfully
        else:  # EMPTY
            return []
        rr += dr
        cc += dc
    return []  # ran off board without closing bracket


def flips_for_move(board: Board, player: str, r: int, c: int) -> List[Tuple[int, int]]:
    """
    Returns list of all stones to flip if player plays at (r,c), or [] if illegal.
    """
    if not in_bounds(r, c) or board.cell(r, c) != EMPTY:
        return []
    flips: List[Tuple[int, int]] = []
    for dr, dc in DIRS:
        flips.extend(_line_flips(board, player, r, c, dr, dc))
    return flips


def valid_moves(board: Board, player: str) -> List[Tuple[int, int]]:
    """
    All legal coordinates where placing a stone flips at least one opponent stone.
    """
    out: List[Tuple[int, int]] = []
    # Small optimization: only consider empties adjacent to at least one opponent stone.
    opp = opponent(player)
    adj_candidates: set[Tuple[int, int]] = set()
    for r in range(SIZE):
        for c in range(SIZE):
            if board.cell(r, c) == opp:
                for dr, dc in DIRS:
                    rr, cc = r + dr, c + dc
                    if in_bounds(rr, cc) and board.cell(rr, cc) == EMPTY:
                        adj_candidates.add((rr, cc))

    for (r, c) in adj_candidates:
        if flips_for_move(board, player, r, c):
            out.append((r, c))

    # Deterministic order (row-major)
    out.sort()
    return out


def apply_move(board: Board, player: str, r: int, c: int) -> Board:
    """
    Returns a NEW Board with the move applied (pure/immutable).
    Raises IllegalMoveError if the move is not legal.
    """
    flips = flips_for_move(board, player, r, c)
    if not flips:
        raise IllegalMoveError(f"Illegal move for {player} at {(r, c)}")

    rows = board.to_rows()
    rows[r][c] = player
    for rr, cc in flips:
        rows[rr][cc] = player
    return Board.from_rows(rows)


def has_any_move(board: Board, player: str) -> bool:
    return len(valid_moves(board, player)) > 0


def is_game_over(board: Board) -> bool:
    """
    In Othello, the game ends when neither player has a legal move
    or the board is full.
    """
    b, w, e = board.counts()
    if e == 0:
        return True
    return not (has_any_move(board, BLACK) or has_any_move(board, WHITE))


def score(board: Board) -> Tuple[int, int]:
    """
    Returns (black_count, white_count).
    """
    b, w, _ = board.counts()
    return b, w


# ---------- Built-in smoke test (standard library only) ----------

def _smoke_test() -> None:  # pragma: no cover
    print("[SMOKE] Creating initial board…")
    b = Board.initial()
    print(b)

    print("[SMOKE] Valid moves for BLACK (should be 4):", valid_moves(b, BLACK))
    print("[SMOKE] Valid moves for WHITE (should be 4):", valid_moves(b, WHITE))

    # Apply a standard opening: BLACK plays at (2,3) i.e., row=2,col=3
    move = (2, 3)
    print(f"[SMOKE] Applying BLACK move {move} …")
    b = apply_move(b, BLACK, *move)
    print(b)

    print("[SMOKE] Now WHITE should have moves and game not over:")
    print("WHITE moves =", valid_moves(b, WHITE))
    print("Game over? =", is_game_over(b))

    # Quick illegal move check
    try:
        apply_move(b, WHITE, 0, 0)
        raise AssertionError("Expected IllegalMoveError not raised")
    except IllegalMoveError:
        print("[SMOKE] Caught expected IllegalMoveError for illegal move.")

    print("[SMOKE] OK")


if __name__ == "__main__":  # pragma: no cover
    _smoke_test()
