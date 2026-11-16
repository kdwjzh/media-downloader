class BridgeApi:
    """Methods exposed to the frontend through pywebview's js_api."""

    def ping(self) -> dict[str, object]:
        return {"ok": True, "data": "pong"}
