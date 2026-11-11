from app.bridge.api import BridgeApi


def test_ping_returns_pong() -> None:
    assert BridgeApi().ping() == "pong"
