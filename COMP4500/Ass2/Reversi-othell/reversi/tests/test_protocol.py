import pytest

from reversi.protocol import (
    encode_new_game, decode_new_game,
    encode_move, decode_move, parse_tcp_line, decode_token,
    PASS, DRAW, YOU_WIN, YOU_LOSE, ERROR, MOVE,
    PORT_MIN, PORT_MAX,
)
from reversi.errors import ProtocolError


# ---------- NEW GAME (UDP) ----------
def test_new_game_roundtrip_ok():
    for p in (PORT_MIN, 9050, PORT_MAX):
        s = encode_new_game(p)
        assert s == f"NEW GAME:{p}"
        assert decode_new_game(s) == p

def test_new_game_malformed_and_range():
    with pytest.raises(ProtocolError):
        decode_new_game("NEW GAME")  # missing colon/port
    with pytest.raises(ProtocolError):
        decode_new_game("NEW GAME:abc")
    with pytest.raises(ProtocolError):
        decode_new_game(f"NEW GAME:{PORT_MIN-1}")
    with pytest.raises(ProtocolError):
        decode_new_game(f"NEW GAME:{PORT_MAX+1}")


# ---------- MOVE (TCP) ----------
def test_move_roundtrip_ok():
    for r, c in [(0,0), (2,3), (7,7)]:
        s = encode_move(r, c)
        assert s == f"MOVE:{r},{c}"
        m = decode_move(s)
        assert (m.row, m.col) == (r, c)

def test_move_invalid_format_or_bounds():
    with pytest.raises(ProtocolError):
        decode_move("MOVE:")
    with pytest.raises(ProtocolError):
        decode_move("MOVE:2")
    with pytest.raises(ProtocolError):
        decode_move("MOVE:2,x")
    with pytest.raises(ProtocolError):
        decode_move("MOVE:-1,0")
    with pytest.raises(ProtocolError):
        decode_move("MOVE:0,8")


# ---------- TOKENS (TCP) ----------
@pytest.mark.parametrize("tok", [PASS, DRAW, YOU_WIN, YOU_LOSE, ERROR])
def test_tokens_decode(tok):
    t = decode_token(tok)
    assert t.kind == tok

def test_tokens_bad():
    with pytest.raises(ProtocolError):
        decode_token("WIN")  # not allowed
    with pytest.raises(ProtocolError):
        decode_token("PASS ")  # trailing space not equal


# ---------- Generic parse ----------
def test_parse_tcp_line():
    assert decode_move("MOVE:2,3") == parse_tcp_line("MOVE:2,3")
    assert decode_token("PASS") == parse_tcp_line("PASS")
    with pytest.raises(ProtocolError):
        parse_tcp_line("HELLO:WORLD")
