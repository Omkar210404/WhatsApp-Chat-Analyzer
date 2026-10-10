"""Analysis tests.

Most of them use a tiny invented chat, small enough that every expected number
below was worked out by hand. The rest check that the totals of the synthetic
sample agree with each other and with what the generator wrote.
"""

from datetime import datetime

import pytest

from scripts import generate_sample_chat as generator
from whatsapp_analyzer import analysis
from whatsapp_analyzer.parser import parse_chat

GRIN = "\N{GRINNING FACE}"
THUMB = "\N{THUMBS UP SIGN}\N{EMOJI MODIFIER FITZPATRICK TYPE-4}"

ASHA_1 = f"Good morning team {GRIN}"
BEN_1 = "morning! see https://example.com/a and https://example.org/b"
BEN_2 = f"The hike was great, great views {GRIN}{GRIN}"
CLEO_1 = "I don't like the rain"
ASHA_2 = f"Packing:\nboots\nmap {THUMB}"

# 1 March 2026 is a Sunday, 4 March 2026 is a Wednesday.
TINY_CHAT = f"""\
01/03/2026, 09:00 - Messages and calls are end-to-end encrypted.
01/03/2026, 09:00 - Asha created group "Test"
01/03/2026, 09:05 - Asha: {ASHA_1}
01/03/2026, 09:06 - Ben: {BEN_1}
01/03/2026, 09:07 - Asha: <Media omitted>
01/03/2026, 21:30 - Ben: {BEN_2}
02/03/2026, 21:45 - Asha: This message was deleted
04/03/2026, 08:15 - Cleo: {CLEO_1}
04/03/2026, 08:16 - Cleo: <Media omitted>
04/03/2026, 08:17 - Asha: {ASHA_2}
04/03/2026, 08:18 - Ben left
"""


@pytest.fixture(scope="module")
def tiny():
    result = parse_chat(TINY_CHAT, date_order="dmy")
    assert len(result.messages) == 11
    return result.to_dataframe()


@pytest.fixture(scope="module")
def empty():
    return parse_chat("").to_dataframe()


# --- overall ----------------------------------------------------------------


def test_overall_stats(tiny):
    assert analysis.overall_stats(tiny) == {
        "messages": 7,  # 5 text + 2 media; the deleted one and the 3 notices do not count
        "text_messages": 5,
        "words": 20,  # 3 + 3 + 6 + 5 + 3
        "media": 2,
        "links": 2,
        "deleted": 1,
        "people": 3,
        "first_message": datetime(2026, 3, 1, 9, 5),
        "last_message": datetime(2026, 3, 4, 8, 17),
        "active_days": 2,
    }


def test_overall_stats_of_an_empty_chat(empty):
    stats = analysis.overall_stats(empty)
    assert stats["messages"] == stats["words"] == stats["media"] == stats["links"] == 0
    assert stats["people"] == stats["active_days"] == stats["deleted"] == 0
    assert stats["first_message"] is None and stats["last_message"] is None


# --- people -----------------------------------------------------------------


def test_people_are_ordered_by_activity_then_name(tiny):
    assert analysis.people(tiny) == ["Asha", "Ben", "Cleo"]


def test_per_person_stats(tiny):
    table = analysis.per_person_stats(tiny)
    assert list(table.columns) == analysis.PERSON_COLUMNS
    rows = {row["person"]: row for row in table.to_dict("records")}
    assert list(rows) == ["Asha", "Ben", "Cleo"]

    assert rows["Asha"] == {
        "person": "Asha",
        "messages": 3,
        "share_pct": 42.9,  # 3 of 7
        "words": 6,
        "avg_words": 3.0,  # 6 words over 2 text messages
        "avg_chars": (len(ASHA_1) + len(ASHA_2)) / 2,
        "media": 1,
        "links": 0,
    }
    assert rows["Ben"] == {
        "person": "Ben",
        "messages": 2,
        "share_pct": 28.6,
        "words": 9,
        "avg_words": 4.5,
        "avg_chars": (len(BEN_1) + len(BEN_2)) / 2,
        "media": 0,
        "links": 2,
    }
    assert rows["Cleo"]["messages"] == 2
    assert rows["Cleo"]["avg_words"] == 5.0
    assert rows["Cleo"]["media"] == 1


def test_per_person_stats_of_an_empty_chat(empty):
    table = analysis.per_person_stats(empty)
    assert table.empty
    assert list(table.columns) == analysis.PERSON_COLUMNS


def test_filter_by_person(tiny):
    ben = analysis.filter_sender(tiny, "Ben")
    assert set(ben["sender"]) == {"Ben"}
    stats = analysis.overall_stats(ben)
    assert (stats["messages"], stats["words"], stats["links"], stats["media"], stats["people"]) == (2, 9, 2, 0, 1)
    assert analysis.filter_sender(tiny, None) is tiny
    assert analysis.filter_sender(tiny, "Nobody").empty


# --- time -------------------------------------------------------------------


def test_messages_per_day_fills_quiet_days(tiny):
    table = analysis.messages_per_day(tiny)
    assert [d.strftime("%Y-%m-%d") for d in table["date"]] == ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04"]
    assert table["messages"].tolist() == [4, 0, 0, 3]


def test_messages_per_hour(tiny):
    table = analysis.messages_per_hour(tiny)
    assert table["hour"].tolist() == list(range(24))
    busy = {row.hour: row.messages for row in table.itertuples() if row.messages}
    assert busy == {8: 3, 9: 3, 21: 1}


def test_messages_per_weekday(tiny):
    table = analysis.messages_per_weekday(tiny)
    assert table["weekday"].tolist() == analysis.WEEKDAYS
    assert table["messages"].tolist() == [0, 0, 3, 0, 0, 0, 4]


def test_weekday_hour_heatmap(tiny):
    table = analysis.weekday_hour_heatmap(tiny)
    assert len(table) == 7 * 24
    busy = {(row.weekday, row.hour): row.messages for row in table.itertuples() if row.messages}
    assert busy == {("Sunday", 9): 3, ("Sunday", 21): 1, ("Wednesday", 8): 3}


def test_time_tables_of_an_empty_chat(empty):
    assert analysis.messages_per_day(empty).empty
    assert analysis.messages_per_hour(empty)["messages"].tolist() == [0] * 24
    assert analysis.messages_per_weekday(empty)["messages"].tolist() == [0] * 7
    heatmap = analysis.weekday_hour_heatmap(empty)
    assert len(heatmap) == 168 and heatmap["messages"].sum() == 0


# --- words and emojis -------------------------------------------------------


def test_top_words_skip_stopwords_links_and_placeholders(tiny):
    table = analysis.top_words(tiny, n=50)
    assert table.to_dict("records")[:3] == [
        {"word": "great", "count": 2},
        {"word": "morning", "count": 2},
        {"word": "boots", "count": 1},
    ]
    words = set(table["word"])
    assert words == {"great", "morning", "boots", "good", "hike", "like", "map", "packing", "rain", "see", "team", "views"}
    # stopwords, link parts, media and deleted placeholders, system notices
    assert not words & {"the", "don't", "https", "example", "media", "omitted", "deleted", "created", "left"}


def test_top_words_limit_and_custom_stopwords(tiny):
    assert len(analysis.top_words(tiny, n=2)) == 2
    table = analysis.top_words(tiny, n=50, extra_stopwords={"GREAT", "boots"})
    assert table.iloc[0].to_dict() == {"word": "morning", "count": 2}
    assert not set(table["word"]) & {"great", "boots"}


def test_top_emojis(tiny):
    assert analysis.top_emojis(tiny).to_dict("records") == [
        {"emoji": GRIN, "count": 3},
        {"emoji": THUMB, "count": 1},
    ]
    assert len(analysis.top_emojis(tiny, n=1)) == 1


def test_words_and_emojis_of_an_empty_chat(empty):
    assert analysis.top_words(empty).empty
    assert analysis.top_emojis(empty).empty
    assert list(analysis.top_words(empty).columns) == ["word", "count"]


# --- the synthetic sample ---------------------------------------------------


def test_sample_totals_match_the_generator(sample_frame):
    events = generator.build_events()
    stats = analysis.overall_stats(sample_frame)
    assert stats["messages"] == sum(e.kind in ("text", "media") for e in events)
    assert stats["media"] == sum(e.kind == "media" for e in events)
    assert stats["deleted"] == sum(e.kind == "deleted" for e in events)
    assert stats["links"] == sum(e.text.count("https://") for e in events if e.kind == "text")
    assert stats["people"] == len({e.sender for e in events if e.sender})


def test_sample_views_add_up_to_the_same_total(sample_frame):
    total = analysis.overall_stats(sample_frame)["messages"]
    people = analysis.per_person_stats(sample_frame)
    assert people["messages"].sum() == total
    assert people["share_pct"].sum() == pytest.approx(100, abs=0.5)
    assert people["messages"].is_monotonic_decreasing
    assert analysis.messages_per_day(sample_frame)["messages"].sum() == total
    assert analysis.messages_per_hour(sample_frame)["messages"].sum() == total
    assert analysis.messages_per_weekday(sample_frame)["messages"].sum() == total
    assert analysis.weekday_hour_heatmap(sample_frame)["messages"].sum() == total


def test_sample_person_filter_matches_the_people_table(sample_frame):
    table = analysis.per_person_stats(sample_frame).set_index("person")
    for person in analysis.people(sample_frame):
        stats = analysis.overall_stats(analysis.filter_sender(sample_frame, person))
        assert stats["messages"] == table.loc[person, "messages"]
        assert stats["words"] == table.loc[person, "words"]
        assert stats["people"] == 1


def test_sample_top_words_contain_no_stopwords_or_placeholders(sample_frame):
    words = set(analysis.top_words(sample_frame, n=200)["word"])
    assert words
    assert not words & {"the", "and", "is", "media", "omitted", "https", "example"}
