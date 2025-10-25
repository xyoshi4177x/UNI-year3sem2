#   reversi/protocol.py
#   Zachary Chan c3468750

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Tuple

from .errors import ProtocolError

# ---- Message constants (spec) ----
NEW_GAME = "NEW GAME"   # UDP payload prefix: "NEW GAME:<port>"
MOVE     = "MOVE"       # TCP line: "MOVE:row,col"
PASS     = "PASS"       # TCP line
YOU_WIN  = "YOU WIN"    # TCP line
YOU_LOSE = "YOU LOSE"   # TCP line
DRAW     = "DRAW"       # TCP line
ERROR    = "ERROR"      # TCP line

# Gameplay port constraints
PORT_MIN = 9000
PORT_MAX = 9100

# Board limits (we use 0-based coordinates on the wire to match our engine/UI)
ROW_MIN = 0
ROW_MAX = 7
COL_MIN = 0
COL_MAX = 7

# Precompiled patterns (strict)
_RE_NEW_GAME = re.compile(rf"^{re.escape(NEW_GAME)}:(\d+)$")
_RE_MOVE     = re.compile(rf"^{MOVE}:(-?\d+),(-?\d+)$")


# ---- Dataclasses for typed decode results ----
@dataclass(frozen=True)
class MsgMove:
    row: int
    col: int

@dataclass(frozen=True)
class MsgToken:
    # One of: PASS / YOU WIN / YOU LOSE / DRAW / ERROR
    kind: Literal["PASS", "YOU WIN", "YOU LOSE", "DRAW", "ERROR"]


# UDP: NEW GAME helpers
def encode_new_game(port: int) -> str:
    """Return UDP broadcast payload 'NEW GAME:<port>'."""
    _validate_port(port)
    return f"{NEW_GAME}:{port}"

def decode_new_game(line: str) -> int:
    """
    Parse 'NEW GAME:<port>' and return port.
    Raise ProtocolError for malformed or out-of-range.
    """
    s = _strip_line(line)
    m = _RE_NEW_GAME.match(s)
    if not m:
        raise ProtocolError(f"Malformed NEW GAME: {line!r}")
    port = int(m.group(1))
    _validate_port(port)
    return port


# TCP: move & token helpers
def encode_move(row: int, col: int) -> str:
    """Return 'MOVE:r,c' with 0-based coords."""
    _validate_coord(row, col)
    return f"{MOVE}:{row},{col}"

def decode_move(line: str) -> MsgMove:
    """
    Parse 'MOVE:r,c' (0-based). Raise ProtocolError if malformed or out of bounds.
    """
    s = _strip_line(line)
    m = _RE_MOVE.match(s)
    if not m:
        raise ProtocolError(f"Malformed MOVE: {line!r}")
    r, c = int(m.group(1)), int(m.group(2))
    _validate_coord(r, c)
    return MsgMove(r, c)

def is_token(line: str) -> bool:
    """True if line is exactly one of the token messages."""
    return _token_kind_or_none(line) is not None

def decode_token(line: str) -> MsgToken:
    """Decode PASS / YOU WIN / YOU LOSE / DRAW / ERROR → MsgToken."""
    kind = _token_kind_or_none(line)
    if kind is None:
        raise ProtocolError(f"Not a valid token: {line!r}")
    return MsgToken(kind)


# General parsing helpers
def parse_tcp_line(line: str) -> MsgMove | MsgToken:
    """
    Parse any TCP message into MsgMove or MsgToken.
    - MOVE:r,c   -> MsgMove
    - PASS/DRAW/YOU WIN/YOU LOSE/ERROR -> MsgToken
    """
    s = _strip_line(line)
    if s.startswith(f"{MOVE}:"):
        return decode_move(s)
    tk = _token_kind_or_none(s)
    if tk is not None:
        return MsgToken(tk)
    raise ProtocolError(f"Unknown/invalid TCP message: {line!r}")


# Internal validators
def _validate_port(port: int) -> None:
    if not (PORT_MIN <= port <= PORT_MAX):
        raise ProtocolError(f"Gameplay port must be in [{PORT_MIN}..{PORT_MAX}], got {port}")

def _validate_coord(row: int, col: int) -> None:
    if not (ROW_MIN <= row <= ROW_MAX and COL_MIN <= col <= COL_MAX):
        raise ProtocolError(f"Row/col out of bounds (0..7): {(row, col)}")

def _strip_line(line: str) -> str:
    # Strip trailing CR/LF and surrounding whitespace, but do NOT allow embedded spaces for tokens.
    return line.rstrip("\r\n")

def _token_kind_or_none(line: str) -> MsgToken["kind"] | None:
    s = _strip_line(line)
    if   s == PASS:    return PASS
    elif s == DRAW:    return DRAW
    elif s == YOU_WIN: return YOU_WIN
    elif s == YOU_LOSE:return YOU_LOSE
    elif s == ERROR:   return ERROR
    return None
