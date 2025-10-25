from reversi.net.udp_discovery import _choose_free_tcp_port
from reversi.protocol import PORT_MIN, PORT_MAX

def test_choose_free_tcp_port_in_range():
    p = _choose_free_tcp_port()
    assert p is None or (PORT_MIN <= p <= PORT_MAX)
