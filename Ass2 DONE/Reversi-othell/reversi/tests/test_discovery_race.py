from reversi.net.udp_discovery import _prefer_peer, _tie_breaker_key

def test_tie_breaker_prefers_earlier_time():
    me = (10.0, "192.168.1.50", 9050)
    peer = (9.9, "192.168.1.99", 9050)
    assert _prefer_peer(*me, *peer) is True

def test_tie_breaker_uses_ip_then_port_on_equal_time():
    t = 10.0
    # same time, lower IP should win
    assert _prefer_peer(t, "192.168.1.50", 9050, t, "192.168.1.49", 9099) is True
    # same time+ip, lower port should win
    assert _prefer_peer(t, "192.168.1.50", 9050, t, "192.168.1.50", 9049) is True
    # peer with higher ip/port loses
    assert _prefer_peer(t, "192.168.1.50", 9050, t, "192.168.1.60", 9040) is False
