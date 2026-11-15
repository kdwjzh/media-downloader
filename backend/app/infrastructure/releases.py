"""Asks GitHub which release of this app is the latest."""

import json

from app import REPOSITORY
from app.infrastructure import http

_HOST = "api.github.com"
TIMEOUT = 5


def latest_tag() -> str:
    """The tag of the latest release that is neither a draft nor a pre-release. Raises
    OSError or ValueError: no network, no release yet, a private repository (404), GitHub's
    hourly limit."""
    body = http.get(
        f"https://{_HOST}/repos/{REPOSITORY}/releases/latest",
        (_HOST,),
        1_000_000,
        TIMEOUT,
        {"Accept": "application/vnd.github+json"},
    )
    data = json.loads(body)
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not isinstance(tag, str):
        raise ValueError("the answer has no tag_name")
    return tag
