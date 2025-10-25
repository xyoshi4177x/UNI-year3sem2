class ReversiError(Exception):
    """Base exception for the app."""

class ProtocolError(ReversiError):
    """Invalid or unexpected protocol message."""

class IllegalMoveError(ReversiError):
    """Move not legal under current board state."""
