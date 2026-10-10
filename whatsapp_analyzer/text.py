"""Small text helpers: words, stopwords, emojis and links."""

from __future__ import annotations

import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

import emoji

_STOPWORDS_FILE = Path(__file__).with_name("stopwords_en.txt")

_LINK = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_CURLY_APOSTROPHE = "\N{RIGHT SINGLE QUOTATION MARK}"


def _combining_marks() -> str:
    """A regex character class body holding every Unicode combining mark.

    Python's regex word class leaves these out, which would cut words apart in
    scripts that write vowels as marks (Hindi, Marathi, Tamil, Arabic and more).
    """
    ranges, start, previous = [], None, None
    for code in range(sys.maxunicode + 1):
        if unicodedata.category(chr(code)).startswith("M"):
            if start is None:
                start = code
            previous = code
        elif start is not None:
            ranges.append(f"{chr(start)}-{chr(previous)}")
            start = None
    return "".join(ranges)


# A word starts with a letter or digit and continues with letters, digits,
# combining marks and the zero-width joiners some scripts use inside words.
# Apostrophes are allowed inside (don't, it's).
_JOINERS = "\N{ZERO WIDTH NON-JOINER}\N{ZERO WIDTH JOINER}"
_PART = rf"[^\W_](?:[^\W_]|[{_combining_marks()}{_JOINERS}])*"
_TOKEN = re.compile(rf"{_PART}(?:'{_PART})*")
_HAS_LETTER = re.compile(r"[^\W\d_]")


@lru_cache(maxsize=1)
def english_stopwords() -> frozenset[str]:
    """The bundled English stopword list."""
    lines = _STOPWORDS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip() for line in lines if line.strip() and not line.startswith("#"))


def parse_custom_stopwords(raw: str) -> set[str]:
    """Turn what the user typed (commas, spaces or new lines between words) into a set."""
    return {word.lower() for word in re.split(r"[\s,;]+", raw.replace(_CURLY_APOSTROPHE, "'")) if word}


def extract_links(text: str) -> list[str]:
    return _LINK.findall(text)


def _tokens(text: str) -> list[str]:
    without_links = _LINK.sub(" ", text).replace(_CURLY_APOSTROPHE, "'")
    return _TOKEN.findall(without_links.lower())


def count_words(text: str) -> int:
    """Number of words in a message. Links and emojis are not words."""
    return len(_tokens(text))


def tokenize(text: str, stopwords: frozenset[str] | set[str] = frozenset()) -> list[str]:
    """Lower-case words worth counting: no links, numbers, single letters or stopwords."""
    return [
        token
        for token in _tokens(text)
        if len(token) > 1 and _HAS_LETTER.search(token) and token not in stopwords
    ]


def extract_emojis(text: str) -> list[str]:
    """Every emoji in the text, in order. A skin-toned or joined emoji is one item."""
    if text.isascii():
        return []  # no emoji is plain ASCII, and most messages are, so skip the slow scan
    return [found["emoji"] for found in emoji.emoji_list(text)]
