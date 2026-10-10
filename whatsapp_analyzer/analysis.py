"""Statistics over a parsed chat.

Every function takes the DataFrame made by parser.to_dataframe() and returns
plain numbers or a new DataFrame. Nothing here touches Streamlit, the disk or
the network, so it can be tested and reused on its own.

What counts as what:
    message   a text message or a media placeholder sent by a person
    words     counted in text messages only
    deleted   "This message was deleted" placeholders, reported separately
    system    notices from WhatsApp (joined, left, ...), never counted
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from whatsapp_analyzer.parser import DELETED, MEDIA, TEXT
from whatsapp_analyzer.text import count_words, english_stopwords, extract_emojis, extract_links, tokenize

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

PERSON_COLUMNS = ["person", "messages", "share_pct", "words", "avg_words", "avg_chars", "media", "links"]


def _messages(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that count as messages: text and media sent by a person."""
    return df[df["kind"].isin([TEXT, MEDIA])]


def _texts(df: pd.DataFrame) -> pd.Series:
    return df.loc[df["kind"] == TEXT, "text"]


def people(df: pd.DataFrame) -> list[str]:
    """Everyone who sent a message, most active first (ties in name order)."""
    counts = _messages(df).groupby("sender").size()
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def filter_sender(df: pd.DataFrame, sender: str | None) -> pd.DataFrame:
    """Keep one person's rows. None keeps the whole chat."""
    if sender is None:
        return df
    return df[df["sender"] == sender]


def overall_stats(df: pd.DataFrame) -> dict:
    messages = _messages(df)
    texts = _texts(df)
    stamps = messages["timestamp"]
    return {
        "messages": len(messages),
        "text_messages": len(texts),
        "words": int(sum(count_words(t) for t in texts)),
        "media": int((df["kind"] == MEDIA).sum()),
        "links": int(sum(len(extract_links(t)) for t in texts)),
        "deleted": int((df["kind"] == DELETED).sum()),
        "people": int(messages["sender"].nunique()),
        "first_message": stamps.min().to_pydatetime() if len(stamps) else None,
        "last_message": stamps.max().to_pydatetime() if len(stamps) else None,
        "active_days": int(stamps.dt.date.nunique()) if len(stamps) else 0,
    }


def per_person_stats(df: pd.DataFrame) -> pd.DataFrame:
    """One row per person, most active first. Averages are over text messages."""
    total = len(_messages(df))
    rows = []
    for person in people(df):
        own = df[df["sender"] == person]
        texts = _texts(own)
        words = sum(count_words(t) for t in texts)
        rows.append(
            {
                "person": person,
                "messages": len(_messages(own)),
                "share_pct": round(100 * len(_messages(own)) / total, 1),
                "words": int(words),
                "avg_words": round(words / len(texts), 1) if len(texts) else 0.0,
                "avg_chars": round(sum(len(t) for t in texts) / len(texts), 1) if len(texts) else 0.0,
                "media": int((own["kind"] == MEDIA).sum()),
                "links": int(sum(len(extract_links(t)) for t in texts)),
            }
        )
    return pd.DataFrame(rows, columns=PERSON_COLUMNS)


def messages_per_day(df: pd.DataFrame) -> pd.DataFrame:
    """Messages on each calendar day from the first to the last, quiet days included as 0."""
    stamps = _messages(df)["timestamp"]
    if stamps.empty:
        return pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "messages": pd.Series(dtype="int64")})
    counts = stamps.dt.normalize().value_counts()
    days = pd.date_range(counts.index.min(), counts.index.max(), freq="D")
    counts = counts.reindex(days, fill_value=0)
    return pd.DataFrame({"date": days, "messages": counts.to_numpy()})


def messages_per_hour(df: pd.DataFrame) -> pd.DataFrame:
    """Messages in each hour of the day, 0 to 23."""
    counts = _messages(df)["timestamp"].dt.hour.value_counts().reindex(range(24), fill_value=0)
    return pd.DataFrame({"hour": list(range(24)), "messages": counts.to_numpy()})


def messages_per_weekday(df: pd.DataFrame) -> pd.DataFrame:
    """Messages on each weekday, Monday to Sunday."""
    counts = _messages(df)["timestamp"].dt.weekday.value_counts().reindex(range(7), fill_value=0)
    return pd.DataFrame({"weekday": WEEKDAYS, "messages": counts.to_numpy()})


def weekday_hour_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """Messages for every weekday and hour: 7 x 24 = 168 rows, zeros included."""
    stamps = _messages(df)["timestamp"]
    counts = Counter(zip(stamps.dt.weekday, stamps.dt.hour))
    rows = [
        {"weekday": name, "hour": hour, "messages": counts.get((day, hour), 0)}
        for day, name in enumerate(WEEKDAYS)
        for hour in range(24)
    ]
    return pd.DataFrame(rows, columns=["weekday", "hour", "messages"])


def word_frequencies(df: pd.DataFrame, extra_stopwords=()) -> Counter:
    """How often each word appears, after dropping English and custom stopwords."""
    stopwords = english_stopwords() | {word.lower() for word in extra_stopwords}
    counts: Counter = Counter()
    for text in _texts(df):
        counts.update(tokenize(text, stopwords))
    return counts


def _top(counts: Counter, n: int, column: str) -> pd.DataFrame:
    # Sort by count, then alphabetically, so equal counts always come out in the same order.
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]
    return pd.DataFrame(ranked, columns=[column, "count"])


def top_words(df: pd.DataFrame, n: int = 20, extra_stopwords=()) -> pd.DataFrame:
    return _top(word_frequencies(df, extra_stopwords), n, "word")


def top_emojis(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    counts: Counter = Counter()
    for text in _texts(df):
        counts.update(extract_emojis(text))
    return _top(counts, n, "emoji")
