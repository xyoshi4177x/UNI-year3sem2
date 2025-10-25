import io
from reversi.game.board import Board, BLACK
from reversi.game.rules import valid_moves
from reversi.UI.console import try_parse_algebraic, format_moves, render_board, prompt_move

def test_try_parse_algebraic_valid_and_invalid():
    assert try_parse_algebraic("D3") == (2, 3)
    assert try_parse_algebraic("a8") == (7, 0)
    assert try_parse_algebraic("H1") == (0, 7)
    assert try_parse_algebraic("Z9") is None
    assert try_parse_algebraic("33") is None
    assert try_parse_algebraic("") is None

def test_format_moves_has_human_labels():
    moves = [(2, 3), (2, 4)]
    s = format_moves(moves)
    # Expect entries like "[0] D3, [1] E3"
    assert "[0]" in s and "D3" in s
    assert "[1]" in s and "E3" in s

def test_render_board_smoke(capsys):
    b = Board.initial()
    render_board(b, BLACK, 1)
    out = capsys.readouterr().out
    assert "BLACK to move" in out
    assert "Score:" in out
    assert "ABCDEFGH" in out

def test_prompt_move_happy_path(monkeypatch):
    b = Board.initial()
    moves = valid_moves(b, BLACK)  # 4 moves at start
    # Feed algebraic for the first legal move (whatever it is)
    first = moves[0]
    algebraic = "ABCDEFGH"[first[1]] + str(first[0] + 1)
    fake_stdin = io.StringIO(algebraic + "\n")
    monkeypatch.setattr("sys.stdin", fake_stdin)
    idx = prompt_move(b, BLACK, moves)
    assert idx == 0  # picked the first move

def test_prompt_move_rejects_then_accepts(monkeypatch, capsys):
    b = Board.initial()
    moves = valid_moves(b, BLACK)
    # First try illegal square, then a valid index "1"
    fake_stdin = io.StringIO("A1\n1\n")
    monkeypatch.setattr("sys.stdin", fake_stdin)
    idx = prompt_move(b, BLACK, moves)
    assert idx == 1
