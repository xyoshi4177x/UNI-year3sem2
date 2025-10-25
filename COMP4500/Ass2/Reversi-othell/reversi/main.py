# reversi/main.py
# Zachary Chan c3468750
import argparse
import ipaddress
import logging
import socket
import sys
from . import __version__

from .game.outcome import outcome_token_for, verify_peer_outcome
from .game.board import Board, BLACK, WHITE, opponent
from .game.rules import valid_moves, apply_move, has_any_move, is_game_over, score
from .UI.console import render_board, prompt_move, announce_pass, announce_winner
from .net.udp_discovery import discover_and_connect
from .net.tcp_game import TcpGame
from .protocol import (
    encode_move, decode_move, parse_tcp_line, is_token,
    PASS, DRAW, YOU_WIN, YOU_LOSE, ERROR, MOVE
)
from .errors import ProtocolError, IllegalMoveError


LOG = logging.getLogger("reversi")

PORT_MIN = 9000
PORT_MAX = 9100

# Setup and Helper functions
def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

def valid_broadcast_addr(addr: str) -> str:
    try:
        ip = ipaddress.ip_address(addr)
        if ip.version != 4:
            raise ValueError("Broadcast must be IPv4.")
        return addr
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid broadcast address: {e}")

def valid_broadcast_port(port_s: str) -> int:
    try:
        port = int(port_s)
    except ValueError:
        raise argparse.ArgumentTypeError("Port must be an integer.")
    if not (PORT_MIN <= port <= PORT_MAX):
        raise argparse.ArgumentTypeError(
            f"Broadcast port must be in [{PORT_MIN}..{PORT_MAX}]."
        )
    return port

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="reversi",
        description="Reversi (Othello) P2P client — console UI (hotseat) and scaffold",
    )
    p.add_argument("--broadcast-addr", type=valid_broadcast_addr,
                   help="UDP broadcast address (e.g., 255.255.255.255)")
    p.add_argument("--broadcast-port", type=valid_broadcast_port,
                   help=f"UDP broadcast port in [{PORT_MIN}..{PORT_MAX}]")
    p.add_argument("--verbose", action="store_true",
                   help="Enable verbose debug logging.")
    p.add_argument("--hotseat", action="store_true",
                   help="Run local 2-player hotseat mode (no networking).")
    p.add_argument("--discover-window", type=float, default=5.0,
               help="Seconds to wait in each discovery/accept window (default: 5.0).")
    p.add_argument("--tcp-echo", action="store_true",
               help="After discovery, run a tiny TCP handshake (P1 sends HELLO, P2 replies ACK).")
    p.add_argument("--play", action="store_true",
               help="Find a peer via UDP and play a full networked game.")
    p.add_argument("--log-json", action="store_true",
               help="Log in JSON lines (one object per line).")
    p.add_argument("--log-file", type=str, default=None,
               help="Optional path to write logs to (in addition to stdout).")
    p.add_argument("--trace-wire", action="store_true",
               help="Trace protocol SEND/RECV lines (safe for marking).")

    return p.parse_args(argv)

def _close_quiet(socklike):
    try:
        socklike.close()
    except Exception:
        pass

def _send_error_and_close(tg: TcpGame, log_reason: str) -> int:
    LOG.error("Protocol error: %s", log_reason)
    try:
        tg.send_line(ERROR)
    except Exception:
        pass
    _close_quiet(tg)
    return 1


def require_broadcast_args(args):
    if args.broadcast_addr is None or args.broadcast_port is None:
        raise SystemExit(
            "Error: --broadcast-addr and --broadcast-port are required unless --hotseat is set."
        )
def _send_outcome_and_close(tg: TcpGame, my_color: str, board: Board) -> int:
    # Compute my perspective and send it, then close (peer will verify on receipt).
    tok = outcome_token_for(board, my_color)
    try:
        tg.send_line(tok)
    finally:
        announce_winner(*score(board))
        tg.close()
    return 0

# the actual game loops
def run_network_game(broadcast_addr: str, broadcast_port: int, window: float = 5.0) -> int:
    LOG.info("Starting discovery window (%.1fs)…", window)
    role, sock, peer, gport = discover_and_connect(broadcast_addr, broadcast_port, window=window)
    LOG.info("Matched! role=%s  peer=%s  gameplay_port=%s", role, peer, gport)

    tg = TcpGame.from_connected(sock)
    tg.set_timeout(300.0)
    try:
        board = Board.initial()
        my_color  = BLACK if role == "P1" else WHITE
        opp_color = WHITE if my_color == BLACK else BLACK
        to_move = BLACK  # Reversi: BLACK starts (Player 1)
        move_num = 1
        consecutive_passes = 0

        while True:
            render_board(board, to_move, move_num)

            # If board already terminal (full/no moves), finish with outcome exchange
            if is_game_over(board):
                return _send_outcome_and_close(tg, my_color, board)

            if to_move == my_color:
                # ----- My turn -----
                moves = valid_moves(board, my_color)
                if not moves:
                    announce_pass(my_color)
                    tg.send_line(PASS)
                    consecutive_passes += 1

                    # If opponent also cannot move, end the game now
                    if not has_any_move(board, opp_color) or consecutive_passes >= 2:
                        return _send_outcome_and_close(tg, my_color, board)

                    # Hand over turn
                    to_move = opp_color
                    continue

                # Have legal moves: prompt strictly from this list
                choice = prompt_move(board, my_color, moves)
                if choice is None:
                    # User bailed; send ERROR to avoid leaving peer hanging
                    try:
                        tg.send_line(ERROR)
                    except Exception:
                        pass
                    tg.close()
                    LOG.info("User quit. Exiting.")
                    return 0

                r, c = moves[choice]
                # Apply locally (cannot raise)
                board = apply_move(board, my_color, r, c)
                move_num += 1
                consecutive_passes = 0

                # Send to peer
                tg.send_line(encode_move(r, c))

                # Hand over turn
                to_move = opp_color

            else:
                # ----- Opponent's turn -----
                try:
                    line = tg.recv_line()
                except ProtocolError as e:
                    LOG.error("Receive failed: %s", e)
                    tg.close()
                    return 1

                # Handle tokens and moves
                if line == PASS:
                    announce_pass(opp_color)
                    consecutive_passes += 1

                    if not has_any_move(board, my_color) or consecutive_passes >= 2:
                        # Double pass: compute outcome and send (from my side)
                        return _send_outcome_and_close(tg, my_color, board)

                    # I get the turn now
                    to_move = my_color
                    continue

                # Outcome tokens (peer might end the game first). Verify and exit.
                if is_token(line) and line in (YOU_WIN, YOU_LOSE, DRAW):
                    ok = verify_peer_outcome(board, my_color, line)
                    if not ok:
                        # Peer’s token disagrees with our computed result → send ERROR and close.
                        try:
                            tg.send_line(ERROR)
                        finally:
                            tg.close()
                        LOG.error("Outcome mismatch: peer sent %r; local says %r",
                                line, outcome_token_for(board, my_color))
                        return 1
                    # Consistent outcome — accept and exit cleanly.
                    announce_winner(*score(board))
                    tg.close()
                    return 0


                # Expect a MOVE
                if not line.startswith(f"{MOVE}:"):
                    # Unexpected message → error and exit
                    try:
                        tg.send_line(ERROR)
                    finally:
                        tg.close()
                    LOG.error("Unexpected message from peer: %r", line)
                    return 1

                # Decode and validate opponent move
                try:
                    msg = decode_move(line)
                except ProtocolError:
                    try:
                        tg.send_line(ERROR)
                    finally:
                        tg.close()
                    LOG.error("Malformed MOVE from peer: %r", line)
                    return 1

                try:
                    board = apply_move(board, opp_color, msg.row, msg.col)
                except IllegalMoveError:
                    try:
                        tg.send_line(ERROR)
                    finally:
                        tg.close()
                    LOG.error("Illegal MOVE from peer at (%s,%s)", msg.row, msg.col)
                    return 1

                move_num += 1
                consecutive_passes = 0
                # Hand over turn to me
                to_move = my_color

    finally:
        # Safety close if still open
        try:
            tg.close()
        except Exception:
            pass


    
# ensuring only one game loop runs
def run_hotseat() -> int:
    """
    Two players on one terminal.
    - BLACK moves first
    - Only valid moves are presented
    - Auto-pass if no move; double pass ends the game
    """
    LOG.info("Starting HOTSEAT game (no networking).")
    board = Board.initial()
    player = BLACK  # BLACK goes first
    consecutive_passes = 0
    move_number = 1

    while True:
        render_board(board, player, move_number)

        # Check if the board/game is already over
        if is_game_over(board):
            b, w = score(board)
            announce_winner(b, w)
            return 0

        moves = valid_moves(board, player)

        if not moves:
            # Auto-pass for this player
            consecutive_passes += 1
            announce_pass(player)
            # If both players passed in a row → end
            other_can_move = has_any_move(board, BLACK if player == WHITE else WHITE)
            if not other_can_move or consecutive_passes >= 2:
                b, w = score(board)
                announce_winner(b, w)
                return 0
            # Switch player
            player = WHITE if player == BLACK else BLACK
            continue

        # We have at least one legal move — prompt user to pick
        consecutive_passes = 0
        choice = prompt_move(board, player, moves)
        if choice is None:
            LOG.info("User quit. Exiting.")
            return 0

        r, c = moves[choice]
        board = apply_move(board, player, r, c)
        player = WHITE if player == BLACK else BLACK
        move_number += 1

# Runnable main
def main(argv=None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)

    LOG.info("Reversi v%s starting…", __version__)
    if args.hotseat:
        # Hotseat mode ignores broadcast args
        return run_hotseat()
    # Networked mode
    if args.play:
        require_broadcast_args(args)
        return run_network_game(args.broadcast_addr, args.broadcast_port, window=5.0)

   # Networking path
    if args.discover or args.tcp_echo:
        require_broadcast_args(args)
        from .net.udp_discovery import discover_and_connect
        from .net.tcp_game import TcpGame
        LOG.info("Starting discovery window (%.1fs)…", 5.0)
        role, sock, peer, gport = discover_and_connect(args.broadcast_addr, args.broadcast_port, window=5.0)
        LOG.info("Matched! role=%s  peer=%s  gameplay_port=%s", role, peer, gport)

        if args.tcp_echo:
            LOG.info("Starting TCP echo handshake…")
            tg = TcpGame.from_connected(sock)
            try:
                board = Board.initial()
                my_color  = BLACK if role == "P1" else WHITE
                opp_color = WHITE if my_color == BLACK else BLACK
                to_move = BLACK
                move_num = 1
                consecutive_passes = 0

                while True:
                    render_board(board, to_move, move_num)

                    if is_game_over(board):
                        return _send_outcome_and_close(tg, my_color, board)

                    if to_move == my_color:
                        # ----- My turn -----
                        moves = valid_moves(board, my_color)
                        if not moves:
                            announce_pass(my_color)
                            tg.send_line(PASS)
                            consecutive_passes += 1
                            if not has_any_move(board, opp_color) or consecutive_passes >= 2:
                                return _send_outcome_and_close(tg, my_color, board)
                            to_move = opp_color
                            continue

                        choice = prompt_move(board, my_color, moves)
                        if choice is None:
                            # user aborted → send ERROR and exit
                            return _send_error_and_close(tg, "user aborted on own turn")

                        r, c = moves[choice]
                        board = apply_move(board, my_color, r, c)
                        move_num += 1
                        consecutive_passes = 0
                        tg.send_line(encode_move(r, c))
                        to_move = opp_color

                    else:
                        # ----- Opponent's turn -----
                        try:
                            line = tg.recv_line()
                        except ProtocolError as e:
                            LOG.error("Receive failed: %s", e)
                            _close_quiet(tg)
                            return 1

                        # ERROR from peer: print & exit
                        if line == ERROR:
                            LOG.error("Received ERROR from peer. Exiting.")
                            _close_quiet(tg)
                            return 1

                        # PASS from peer
                        if line == PASS:
                            announce_pass(opp_color)
                            consecutive_passes += 1
                            if not has_any_move(board, my_color) or consecutive_passes >= 2:
                                return _send_outcome_and_close(tg, my_color, board)
                            to_move = my_color
                            continue

                        # Outcome tokens: verify against my board
                        if is_token(line) and line in (YOU_WIN, YOU_LOSE, DRAW):
                            ok = verify_peer_outcome(board, my_color, line)
                            if not ok:
                                return _send_error_and_close(
                                    tg,
                                    f"outcome mismatch: peer sent {line!r}, local expects {outcome_token_for(board, my_color)!r}",
                                )
                            announce_winner(*score(board))
                            _close_quiet(tg)
                            return 0

                        # Expect MOVE:r,c
                        if not line.startswith(f"{MOVE}:"):
                            return _send_error_and_close(tg, f"unexpected message from peer: {line!r}")

                        # Decode & validate coordinates
                        try:
                            msg = decode_move(line)
                        except ProtocolError:
                            return _send_error_and_close(tg, f"malformed MOVE from peer: {line!r}")

                        # Apply the opponent move against my local rules
                        try:
                            board = apply_move(board, opp_color, msg.row, msg.col)
                        except IllegalMoveError:
                            return _send_error_and_close(tg, f"illegal MOVE from peer at ({msg.row},{msg.col})")

                        move_num += 1
                        consecutive_passes = 0
                        to_move = my_color

            except KeyboardInterrupt:
                # Best-effort courtesy ERROR so the other side doesn’t hang
                try:
                    tg.send_line(ERROR)
                except Exception:
                    pass
                _close_quiet(tg)
                LOG.warning("Interrupted by user (Ctrl+C).")
                return 1


        # Default discover-only path: just close.
        # Default scaffold
        require_broadcast_args(args)
        LOG.info("Broadcast addr: %s", args.broadcast_addr)
        LOG.info("Broadcast port: %s", args.broadcast_port)
        LOG.info("Use --hotseat to play locally, --play to play over network, or --discover/--tcp-echo for transport tests.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
