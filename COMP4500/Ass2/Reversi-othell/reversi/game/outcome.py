# reversi/game/outcome.py
# Zachary Chan c3468750
from __future__ import annotations
from typing import Literal

from .board import BLACK, WHITE
from .rules import score
from ..protocol import YOU_WIN, YOU_LOSE, DRAW

Token = Literal["YOU WIN", "YOU LOSE", "DRAW"]

def outcome_token_for(board, my_color: str) -> Token:
    """
    Token to SEND TO THE PEER per spec (peer-addressed).
    - If peer is winning: "YOU WIN"
    - If draw: "DRAW"
    - If I am winning: "YOU LOSE"
    """
    b, w = score(board)
    if b == w:
        return DRAW
    if my_color == BLACK:
        # If Black is winning, peer (White) loses
        return YOU_LOSE if b > w else YOU_WIN
    else:  # my_color == WHITE
        return YOU_LOSE if w > b else YOU_WIN

def verify_peer_outcome(board, my_color: str, peer_token: Token) -> bool:
    """
    Verify a token RECEIVED FROM PEER (which is addressed to ME).
    If I receive "YOU WIN", I should actually be winning, etc.
    """
    b, w = score(board)
    if peer_token == DRAW:
        return b == w
    if my_color == BLACK:
        # Received "YOU WIN" means Black is winning
        return (b > w) if peer_token == YOU_WIN else (w > b)
    else:  # WHITE
        return (w > b) if peer_token == YOU_WIN else (b > w)
