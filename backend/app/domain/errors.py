from enum import StrEnum


class ErrorCode(StrEnum):
    """Why a lookup or download failed. The values are the `error.*` keys of the UI languages."""

    INVALID_URL = "invalidUrl"
    UNSUPPORTED_SITE = "unsupportedSite"
    NOT_FOUND = "notFound"
    PRIVATE = "private"
    AGE_RESTRICTED = "ageRestricted"
    MEMBERS_ONLY = "membersOnly"
    GEO_BLOCKED = "geoBlocked"
    PLAYLIST_NOT_FOUND = "playlistNotFound"
    LIVE_NOT_SUPPORTED = "liveNotSupported"
    NETWORK = "network"
    UNKNOWN = "unknown"


# Retrying any other error cannot succeed: there is no sign-in in this version.
RETRYABLE = frozenset({ErrorCode.NETWORK, ErrorCode.UNKNOWN})


class InvalidTransition(Exception):
    """A DownloadTask was asked to do something its current status does not allow."""
