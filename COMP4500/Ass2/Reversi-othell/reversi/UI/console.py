# reversi/UI/console.py
# Zachary Chan c3468750
from __future__ import annotations

import sys
from typing import List, Optional, Sequence, Tuple

from ..game.board import Board, BLACK, WHITE, SIZE

# Algebraic helpers (A–H, 1–8)
COL_TO_LET = "ABCDEFGH"
LET_TO_COL = {c: i for i, c in enumerate(COL_TO_LET)}
ROW_TO_NUM = [str(i + 1) for i in range(SIZE)]  # "1".."8"


def color_name(player: str) -> str:
    return "BLACK" if player == BLACK else "WHITE"


def render_board(board: Board, player_to_move: str, move_number: int) -> None:
    rows = board.to_rows()
    b, w, e = board.counts()

    # Header
    print()
    print("=" * 40)
    print(f" Move #{move_number} — {color_name(player_to_move)} to move")
    print(f" Score: BLACK={b}  WHITE={w}  Empty={e}")
    print("    " + "".join(COL_TO_LET))

    for r in range(SIZE):
        line = " ".join(rows[r])
        print(f" {r+1:>2}  {line}")
    print("=" * 40)


def format_moves(moves: Sequence[Tuple[int, int]]) -> str:
    """Human-friendly listing with algebraic notation."""
    parts = []
    for i, (r, c) in enumerate(moves):
        parts.append(f"[{i}] {COL_TO_LET[c]}{r+1}")
    return ", ".join(parts)


def try_parse_algebraic(s: str) -> Optional[Tuple[int, int]]:
    """
    Accepts strings like 'd3', 'D3', 'a8'. Returns (row, col) 0-based or None if invalid.
    """
    s = s.strip()
    if len(s) < 2 or len(s) > 3:
        return None
    col_ch = s[0].upper()
    row_str = s[1:]
    if col_ch not in LET_TO_COL:
        return None
    if not row_str.isdigit():
        return None
    row = int(row_str) - 1
    col = LET_TO_COL[col_ch]
    if 0 <= row < SIZE and 0 <= col < SIZE:
        return (row, col)
    return None


def prompt_move(board: Board, player: str, moves: Sequence[Tuple[int, int]]) -> Optional[int]:
    """
    Ask the current player to choose a move.
    Returns the index into `moves`, or None if the user quits.
    """
    print(f"{color_name(player)} legal moves: {format_moves(moves)}")
    print("Enter move by [index] or [algebraic like D3].  (q = quit)")
    while True:
        sys.stdout.write("> ")
        sys.stdout.flush()
        raw = sys.stdin.readline()
        if raw == "":
            # EOF (e.g., Ctrl+D) -> quit
            return None
        raw = raw.strip()
        if raw.lower() in {"q", "quit", "exit"}:
            return None

        # Index path
        if raw.isdigit():
            idx = int(raw)
            if 0 <= idx < len(moves):
                return idx
            else:
                print(f"Index out of range 0..{len(moves)-1}")
                continue

        # Algebraic path
        pos = try_parse_algebraic(raw)
        if pos is not None:
            try_idx = None
            for i, mv in enumerate(moves):
                if mv == pos:
                    try_idx = i
                    break
            if try_idx is not None:
                return try_idx
            else:
                print("That square is not a legal move this turn. Choose from the list.")
                continue

        print("Invalid input. Use an index (e.g., 0) or algebraic (e.g., D3), or 'q' to quit.")


def announce_pass(player: str) -> None:
    print(f"→ {color_name(player)} has no legal moves and PASSES.")


def announce_winner(black_count: int, white_count: int) -> None:
    print()
    print("#" * 40)
    if black_count > white_count:
        print(f"FINAL: BLACK wins {black_count}–{white_count}")
    elif white_count > black_count:
        print(f"FINAL: WHITE wins {white_count}–{black_count}")
    else:
        print(f"FINAL: DRAW {black_count}–{white_count}")
    print("#" * 40)
