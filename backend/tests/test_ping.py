from app.bridge.api import BridgeApi


def test_ping_replies_like_every_other_command() -> None:
    assert BridgeApi().ping() == {"ok": True, "data": "pong"}
