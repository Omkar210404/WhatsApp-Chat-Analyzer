"""Tests for the word, stopword, emoji and link helpers."""

from whatsapp_analyzer.text import (
    count_words,
    english_stopwords,
    extract_emojis,
    extract_links,
    parse_custom_stopwords,
    tokenize,
)

THUMBS_UP_MEDIUM_SKIN = "\N{THUMBS UP SIGN}\N{EMOJI MODIFIER FITZPATRICK TYPE-4}"
WOMAN_CLIMBING = "\N{PERSON CLIMBING}\N{ZERO WIDTH JOINER}\N{FEMALE SIGN}\N{VARIATION SELECTOR-16}"


def test_stopword_list_is_loaded_without_comments():
    stopwords = english_stopwords()
    assert {"the", "and", "don't", "you're"} <= stopwords
    assert not any(word.startswith("#") or word != word.strip().lower() for word in stopwords)
    assert "hike" not in stopwords


def test_tokenize_lower_cases_and_drops_punctuation():
    assert tokenize("Great HIKE, great view!") == ["great", "hike", "great", "view"]


def test_tokenize_drops_links_numbers_and_single_letters():
    assert tokenize("Route B: 12 km, see https://example.com/trails/pine-ridge or www.example.org") == [
        "route",
        "km",
        "see",
        "or",
    ]


def test_tokenize_keeps_apostrophes_straight_or_curly():
    assert tokenize("don't") == ["don't"]
    assert tokenize("don\N{RIGHT SINGLE QUOTATION MARK}t") == ["don't"]


def test_tokenize_removes_stopwords():
    assert tokenize("We don't need the map", english_stopwords()) == ["need", "map"]
    assert tokenize("We don't need the map", english_stopwords() | {"map"}) == ["need"]


def test_tokenize_handles_other_scripts():
    assert tokenize("chalo पहाड़ चलें") == ["chalo", "पहाड़", "चलें"]


def test_count_words_ignores_links_and_emojis():
    assert count_words("I am in") == 3
    assert count_words("see https://example.com/a-b-c now") == 2
    assert count_words("\N{FACE WITH TEARS OF JOY}\N{FACE WITH TEARS OF JOY}") == 0
    assert count_words(f"⛰️ {WOMAN_CLIMBING} {THUMBS_UP_MEDIUM_SKIN}") == 0
    assert count_words("meet at 7") == 3
    assert count_words("") == 0


def test_custom_stopwords_accept_commas_spaces_and_new_lines():
    assert parse_custom_stopwords("Haha, ok\nLOL  yeah;hmm") == {"haha", "ok", "lol", "yeah", "hmm"}
    assert parse_custom_stopwords("   ") == set()


def test_extract_links():
    text = "Route https://example.com/trails/a and www.example.org/b, also http://example.com"
    assert extract_links(text) == ["https://example.com/trails/a", "www.example.org/b,", "http://example.com"]
    assert extract_links("no links here") == []


def test_extract_emojis_counts_repeats():
    laugh = "\N{FACE WITH TEARS OF JOY}"
    assert extract_emojis(f"so funny {laugh}{laugh} ok {laugh}") == [laugh, laugh, laugh]
    assert extract_emojis("plain text :) <3") == []


def test_skin_tone_and_joined_emojis_are_one_emoji_each():
    assert extract_emojis(f"ok {THUMBS_UP_MEDIUM_SKIN} go {WOMAN_CLIMBING}") == [THUMBS_UP_MEDIUM_SKIN, WOMAN_CLIMBING]
