"""MediaInfoService with a fake engine: tidying pasted text, remembering titles, and not
looking the same URL up twice at once."""

import threading

import pytest
from fake_engine import THUMB, WAIT, FakeEngine, info

from app.domain.engine import EngineError, MediaEngine
from app.domain.errors import ErrorCode
from app.domain.media import MediaInfo, PlaylistEntry, PlaylistInfo
from app.services import media_info
from app.services.media_info import MediaInfoService, normalize

URL = "https://youtu.be/abc"


@pytest.mark.parametrize(
    ("pasted", "url"),
    [
        ("https://youtu.be/abc", "https://youtu.be/abc"),
        ("  https://youtu.be/abc \r\n", "https://youtu.be/abc"),
        ("\thttp://youtu.be/abc", "http://youtu.be/abc"),  # http stays http
        ("youtu.be/abc", "https://youtu.be/abc"),
        ("www.youtube.com/watch?v=abc&list=PLx", "https://www.youtube.com/watch?v=abc&list=PLx"),
        ("music.youtube.com", "https://music.youtube.com"),
        ("youtube.com:443/watch?v=abc", "https://youtube.com:443/watch?v=abc"),
        # Not something that looks like a URL: left alone, and the engine refuses it.
        ("hello", "hello"),
        ("", ""),
        ("some words.with a dot", "some words.with a dot"),
        ("youtu.be/a\nyoutu.be/b", "youtu.be/a\nyoutu.be/b"),
        ("ftp://youtu.be/abc", "ftp://youtu.be/abc"),
        ("-U", "-U"),
        ("/watch?v=abc", "/watch?v=abc"),
    ],
)
def test_normalize(pasted: str, url: str) -> None:
    assert normalize(pasted) == url


def service(engine: FakeEngine) -> MediaInfoService:
    checked: MediaEngine = engine  # mypy checks that the fake has the engine's shape
    return MediaInfoService(checked)


def test_lookup_tidies_the_text_and_remembers_title_and_thumbnail() -> None:
    engine = FakeEngine()
    engine.answers[URL] = info(URL, "Song")
    media = service(engine)
    assert media.known(URL) is None
    result = media.lookup(" youtu.be/abc\n")
    assert isinstance(result, MediaInfo) and result.url == URL
    assert engine.fetched == [URL]
    assert media.known(URL) == ("Song", THUMB)


def test_every_available_playlist_entry_is_remembered() -> None:
    engine = FakeEngine()
    playlist = "https://www.youtube.com/playlist?list=PLx"
    engine.answers[playlist] = PlaylistInfo(
        playlist,
        "List",
        "fake",
        (
            PlaylistEntry("https://youtu.be/1", title="One", thumb=THUMB),
            PlaylistEntry("https://youtu.be/2", available=False),
            PlaylistEntry("https://youtu.be/3", title="Three"),
        ),
    )
    media = service(engine)
    media.lookup(playlist)
    assert media.known("https://youtu.be/1") == ("One", THUMB)
    assert media.known("https://youtu.be/2") is None
    assert media.known("https://youtu.be/3") == ("Three", None)
    assert media.known(playlist) is None  # a playlist is not something to download


def test_the_oldest_are_forgotten_beyond_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_info, "CACHE_LIMIT", 2)
    media = service(FakeEngine())
    media.remember("u1", "1")
    media.remember("u2", "2")
    media.remember("u1", "1 again")  # used again: no longer the oldest
    media.remember("u3", "3")
    assert media.known("u2") is None
    assert media.known("u1") == ("1 again", None) and media.known("u3") == ("3", None)


def test_a_url_being_looked_up_is_not_looked_up_a_second_time() -> None:
    engine = FakeEngine()
    media = service(engine)
    results: list[object] = []
    first = threading.Thread(target=lambda: results.append(media.lookup(URL)))
    first.start()
    url, pending = engine.lookups.get(timeout=WAIT)  # the first lookup is now inside the engine
    second = threading.Thread(target=lambda: results.append(media.lookup(f" {URL} ")))
    second.start()
    answer = info(url)
    pending.put(answer)
    first.join(WAIT)
    second.join(WAIT)  # a second engine call would wait for an answer nobody gives
    assert results == [answer, answer]
    assert engine.fetched == [URL]


def test_a_failed_lookup_fails_for_everyone_waiting_and_is_not_remembered() -> None:
    engine = FakeEngine()
    engine.answers[URL] = EngineError(ErrorCode.PRIVATE, "raw text")
    media = service(engine)
    for _ in range(2):
        with pytest.raises(EngineError) as error:
            media.lookup(URL)
        assert error.value.code is ErrorCode.PRIVATE
    assert engine.fetched == [URL, URL]  # asked again: nothing was cached
    assert media.known(URL) is None
