#   reversi/net/udp_discovery.py
#   Zachary Chan c3468750
from __future__ import annotations

import random
import select
import socket
import time
from typing import Optional, Tuple

from ..protocol import (
    encode_new_game,
    decode_new_game,
    PORT_MIN,
    PORT_MAX,
)
from ..errors import ProtocolError


DEFAULT_WINDOW = 5.0  # seconds per wait window


# helper functions
def _tie_breaker_key(ts: float, ip: str, port: int) -> tuple:
    """Lower key wins: earliest timestamp, then ip, then port."""
    return (ts, ip, port)

def _prefer_peer(my_ad_ts: float, my_ip: str, my_port: int,
                 peer_ts: float, peer_ip: str, peer_port: int) -> bool:
    """Return True if peer's advert should win the race."""
    return _tie_breaker_key(peer_ts, peer_ip, peer_port) < _tie_breaker_key(my_ad_ts, my_ip, my_port)


# functions that are for constructing sockets
def _make_udp_listener(bind_port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    SO_REUSEPORT = getattr(socket, "SO_REUSEPORT", None)
    if SO_REUSEPORT is not None:
        try:
            s.setsockopt(socket.SOL_SOCKET, SO_REUSEPORT, 1)
        except OSError:
            pass
    s.bind(("", bind_port))
    s.setblocking(False)
    return s

def _make_udp_broadcaster() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.setblocking(False)
    return s

def _choose_free_tcp_port() -> Optional[int]:
    candidates = list(range(PORT_MIN, PORT_MAX + 1))
    random.shuffle(candidates)
    for p in candidates:
        try:
            test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test.bind(("", p))
            test.close()
            return p
        except OSError:
            continue
    return None

def _make_tcp_listener(port: int, accept_timeout: float) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", port))
    s.listen(1)
    s.settimeout(accept_timeout)
    return s


# the actual UDP discovery protocol functions
def _recv_new_game(udp_sock: socket.socket, timeout: float) -> Optional[Tuple[str, int, Tuple[str, int]]]:
    """
    Wait up to 'timeout' for a NEW GAME:<port> UDP datagram.
    Return (sender_ip, gameplay_port, sender_addr) if seen; else None.
    """
    end = time.time() + timeout
    while time.time() < end:
        r, _, _ = select.select([udp_sock], [], [], max(0.0, end - time.time()))
        if not r:
            continue
        try:
            data, addr = udp_sock.recvfrom(4096)
        except BlockingIOError:
            continue
        if not data:
            continue
        line = data.decode("utf-8", errors="replace").rstrip("\r\n")
        try:
            gameplay_port = decode_new_game(line)
        except ProtocolError:
            continue
        sender_ip = addr[0]
        return (sender_ip, gameplay_port, addr)
    return None

def _broadcast_new_game(udp_bcaster: socket.socket, broadcast_addr: str, broadcast_port: int, gameplay_port: int) -> None:
    payload = encode_new_game(gameplay_port).encode("utf-8")
    udp_bcaster.sendto(payload, (broadcast_addr, broadcast_port))


# main matchmaking function
def discover_and_connect(
    broadcast_addr: str,
    broadcast_port: int,
    window: float = DEFAULT_WINDOW,
) -> Tuple[str, socket.socket, Tuple[str, int], int]:
    """
    Robust matchmaking:
      1) Listen for NEW GAME for 'window' seconds.
         - If seen → connect back as P2 → return.
      2) Otherwise, pick TCP port, listen, broadcast NEW GAME, and wait for either:
         a) An incoming TCP connection (→ P1), OR
         b) A competing NEW GAME advert that wins the tie-breaker (→ switch to P2 and connect),
         all within 'window'. On failure, loop.

    Returns: (role, connected_tcp_sock, peer_sockaddr, gameplay_port)
    """
    udp_listener = _make_udp_listener(broadcast_port)
    udp_bcaster = _make_udp_broadcaster()

    try:
        attempt = 0
        while True:
            attempt += 1
            # STEP 1: passive discovery
            #print(f"[Matchmaking] Attempt {attempt}: listening for NEW GAME adverts...")
            found = _recv_new_game(udp_listener, timeout=window)
            if found:
                sender_ip, gameplay_port, _ = found
                tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_sock.settimeout(window)
                try:
                    tcp_sock.connect((sender_ip, gameplay_port))
                except OSError:
                    tcp_sock.close()
                    continue  # stale advert, try again
                tcp_sock.settimeout(window)
                return "P2", tcp_sock, (sender_ip, gameplay_port), gameplay_port

            # STEP 2: active advertise + race-friendly wait
            # choose a port (fallback if bind fails)
            while True:
                gameplay_port = _choose_free_tcp_port()
                if gameplay_port is None:
                    time.sleep(0.2)
                    continue
                try:
                    listener = _make_tcp_listener(gameplay_port, accept_timeout=window)
                    break
                except OSError:
                    # race between probe and bind; retry
                    time.sleep(0.05)
                    continue

            my_advert_ts = time.time()
            my_ip_guess = socket.gethostbyname(socket.gethostname()) or "255.255.255.255"

            try:
                _broadcast_new_game(udp_bcaster, broadcast_addr, broadcast_port, gameplay_port)

                end = time.time() + window
                while time.time() < end:
                    # Wait on both: listener for TCP accept, UDP for competing adverts
                    timeout = max(0.0, end - time.time())
                    rlist = [listener, udp_listener]
                    r, _, _ = select.select(rlist, [], [], timeout)
                    if not r:
                        continue

                    # Incoming TCP?
                    if listener in r:
                        try:
                            conn, addr = listener.accept()
                        except socket.timeout:
                            pass
                        else:
                            conn.settimeout(window)
                            return "P1", conn, addr, gameplay_port

                    # Competing NEW GAME?
                    if udp_listener in r:
                        try:
                            data, addr = udp_listener.recvfrom(4096)
                        except BlockingIOError:
                            data = None
                        if data:
                            line = data.decode("utf-8", errors="replace").rstrip("\r\n")
                            try:
                                peer_port = decode_new_game(line)
                            except ProtocolError:
                                peer_port = None
                            if peer_port is not None:
                                peer_ip = addr[0]
                                peer_ts = time.time()  # arrival time stands in for advert time
                                if _prefer_peer(my_advert_ts, my_ip_guess, gameplay_port, peer_ts, peer_ip, peer_port):
                                    # Demote myself; connect back as P2
                                    try:
                                        listener.close()
                                    except Exception:
                                        pass
                                    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    tcp_sock.settimeout(window)
                                    try:
                                        tcp_sock.connect((peer_ip, peer_port))
                                    except OSError:
                                        tcp_sock.close()
                                        # Could not connect; keep waiting within the window
                                        continue
                                    tcp_sock.settimeout(window)
                                    return "P2", tcp_sock, (peer_ip, peer_port), peer_port

                # Window expired: no accept and did not switch; retry loop
                try:
                    listener.close()
                except Exception:
                    pass

            finally:
                # ensure listener closed on any exception path above
                try:
                    listener.close()
                except Exception:
                    pass

    finally:
        try:
            udp_listener.close()
        except Exception:
            pass
        try:
            udp_bcaster.close()
        except Exception:
            pass
