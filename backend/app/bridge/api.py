class BridgeApi:
    """Methods exposed to the frontend through pywebview's js_api."""

    def ping(self) -> str:
        return "pong"
