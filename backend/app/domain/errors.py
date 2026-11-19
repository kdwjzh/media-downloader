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
    # Only for a queue item added by URL alone that turned out to be a playlist.
    PLAYLIST_URL = "playlistUrl"
    NETWORK = "network"
    UNKNOWN = "unknown"
    # Only for an app update: the downloaded installer is not the one the release lists.
    CHECKSUM_MISMATCH = "checksumMismatch"


# Retrying any other error cannot succeed: there is no sign-in in this version. A download
# that did not match its checksum is usually a damaged download, so it may.
RETRYABLE = frozenset({ErrorCode.NETWORK, ErrorCode.UNKNOWN, ErrorCode.CHECKSUM_MISMATCH})


class InvalidTransition(Exception):
    """A DownloadTask was asked to do something its current status does not allow."""
