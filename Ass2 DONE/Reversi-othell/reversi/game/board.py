# reversi/game/board.py
# Zachary Chan c3468750

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

# Cell values
EMPTY = "."
BLACK = "B"
WHITE = "W"

# Board dimensions
SIZE = 8

Player = str  # "B" or "W"
Grid = Tuple[Tuple[str, ...], ...]  # immutable (tuple-of-tuples)


def opponent(player: Player) -> Player:
    if player == BLACK:
        return WHITE
    if player == WHITE:
        return BLACK
    raise ValueError(f"Invalid player: {player!r}")


def in_bounds(r: int, c: int) -> bool:
    return 0 <= r < SIZE and 0 <= c < SIZE


@dataclass(frozen=True)
class Board:
    """
    Immutable board wrapper around a tuple-of-tuples grid.

    Use Board.initial() to create a fresh starting position.
    Use Board.from_rows for tests, and Board.to_rows() for debugging.
    """

    grid: Grid

    @staticmethod
    def initial() -> "Board":
        rows: List[List[str]] = [[EMPTY] * SIZE for _ in range(SIZE)]
        mid = SIZE // 2
        # Standard Othello start
        rows[mid - 1][mid - 1] = WHITE  # D4
        rows[mid][mid] = WHITE          # E5
        rows[mid - 1][mid] = BLACK      # E4
        rows[mid][mid - 1] = BLACK      # D5
        return Board(tuple(tuple(r) for r in rows))

    @staticmethod
    def from_rows(rows: Sequence[Sequence[str]]) -> "Board":
        if len(rows) != SIZE or any(len(r) != SIZE for r in rows):
            raise ValueError("Board must be 8x8")
        for rr in rows:
            for cell in rr:
                if cell not in (EMPTY, BLACK, WHITE):
                    raise ValueError(f"Invalid cell: {cell!r}")
        return Board(tuple(tuple(r) for r in rows))

    def to_rows(self) -> List[List[str]]:
        return [list(r) for r in self.grid]

    def cell(self, r: int, c: int) -> str:
        if not in_bounds(r, c):
            raise IndexError("Out of bounds")
        return self.grid[r][c]

    def count(self, player: Player) -> int:
        return sum(cell == player for row in self.grid for cell in row)

    def counts(self) -> Tuple[int, int, int]:
        b = self.count(BLACK)
        w = self.count(WHITE)
        e = SIZE * SIZE - (b + w)
        return b, w, e

    # Pretty string for quick debugging
    def __str__(self) -> str:  # pragma: no cover (cosmetic)
        header = "   " + " ".join(str(c) for c in range(SIZE))
        lines = [header]
        for r in range(SIZE):
            lines.append(f"{r}  " + " ".join(self.grid[r]))
        b, w, e = self.counts()
        lines.append(f"B={b} W={w} E={e}")
        return "\n".join(lines)
