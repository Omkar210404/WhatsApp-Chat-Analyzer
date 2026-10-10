"""Parse an exported WhatsApp chat (.txt) into structured messages.

Everything here is plain in-memory text processing. Nothing is written to disk
and nothing is sent anywhere.

Supported line shapes (see the README for the limits):

    Android   25/12/2023, 21:15 - Mira: Happy holidays!
    Android   12/25/23, 9:15 PM - Mira: Happy holidays!
    iPhone    [25/12/2023, 21:15:03] Mira: Happy holidays!
    iPhone    [12/25/23, 9:15:03 PM] Mira: Happy holidays!
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

TEXT = "text"
MEDIA = "media"
DELETED = "deleted"
SYSTEM = "system"
KINDS = (TEXT, MEDIA, DELETED, SYSTEM)

ANDROID = "android"
IPHONE = "iphone"

DAY_FIRST = "dmy"
MONTH_FIRST = "mdy"
YEAR_FIRST = "ymd"

COLUMNS = ["timestamp", "sender", "text", "kind"]


@dataclass(frozen=True)
class Message:
    timestamp: datetime
    sender: str | None  # None for system messages
    text: str
    kind: str  # one of KINDS


@dataclass
class ParseResult:
    messages: list[Message]
    style: str | None  # ANDROID, IPHONE, or None when nothing was recognised
    date_order: str | None  # DAY_FIRST, MONTH_FIRST or YEAR_FIRST
    date_order_ambiguous: bool  # True when no date in the file settles day/month order
    clock: str | None  # "12h" or "24h"
    unparsed_lines: int  # non-blank lines found before the first message

    def to_dataframe(self) -> pd.DataFrame:
        return to_dataframe(self.messages)


# Invisible direction marks. iPhone puts U+200E at the start of system and
# media lines, Android wraps phone numbers in U+202A ... U+202C.
_MARKS = re.compile("[‎‏‪-‮﻿]")
# No-break spaces. Newer exports put U+202F between the time and AM/PM.
_ODD_SPACES = re.compile("[  ]")

_DATE = r"(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})"
_TIME = r"(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?(?:\s?([AaPp])\.?\s?[Mm]\.?)?"

_HEADERS = {
    ANDROID: re.compile(rf"^{_DATE},?\s+{_TIME}\s+-(?:\s(.*))?$"),
    IPHONE: re.compile(rf"^\[{_DATE},?\s+{_TIME}\]\s?(.*)$"),
}

# The actor in a system line is written as [^:]+ so that an ordinary message
# such as "Mira: I added sugar" can never match.
_WHO = r"[^:]+"
_SYSTEM = re.compile(
    "|".join(
        [
            r"^Messages and calls are end-to-end encrypted\b.*$",
            r"^Messages to this (?:group|chat) are now secured with end-to-end encryption\b.*$",
            rf"^{_WHO} created (?:this )?group\b.*$",
            rf"^{_WHO} added .+$",
            rf"^{_WHO} (?:was|were) added$",
            rf"^{_WHO} removed .+$",
            rf"^{_WHO} (?:was|were) removed$",
            rf"^{_WHO} left$",
            rf"^{_WHO} joined(?: (?:using|via|from) .+)?$",
            rf"^{_WHO} changed (?:the subject|the group|this group|their phone number|to \+).*$",
            rf"^{_WHO} deleted (?:the|this) group\b.*$",
            rf"^{_WHO} pinned a message$",
            rf"^{_WHO} (?:is|are) now an admin$",
            rf"^{_WHO} (?:turned on|turned off|updated|set) (?:the )?(?:disappearing messages|message timer)\b.*$",
            r"^Disappearing messages (?:was|were) turned (?:on|off)\b.*$",
            r"^Your security code with .+ changed\b.*$",
            r"^You (?:blocked|unblocked) this contact\b.*$",
            r"^This chat is with a business account\b.*$",
        ]
    ),
    re.IGNORECASE,
)

_MEDIA = re.compile(
    "|".join(
        [
            r"^<Media omitted>$",
            r"^(?:image|video|audio|sticker|GIF|document|Contact card) omitted$",
            r"^<attached: .+>$",
            r"^.+ \(file attached\)$",
        ]
    ),
    re.IGNORECASE,
)
# iPhone writes documents as "report.pdf • 3 pages document omitted". Only
# trusted when the line also carried the invisible mark iPhone adds.
_MEDIA_MARKED = re.compile(r"^.+ omitted$", re.IGNORECASE)

_DELETED = re.compile(r"^(?:This message was deleted|You deleted this message)\.?$", re.IGNORECASE)
_EDITED_TAG = re.compile(r"\s*<This message was edited>$")


def _to_datetime(groups: tuple, order: str) -> datetime | None:
    """Build a datetime from the regex groups, or None if they are not a real date."""
    a, b, c, hour, minute, second, ampm = groups[:7]
    if order == YEAR_FIRST:
        year, month, day = a, b, c
    elif order == MONTH_FIRST:
        month, day, year = a, b, c
    else:
        day, month, year = a, b, c
    if len(year) not in (2, 4):
        return None
    year_n = int(year) + 2000 if len(year) == 2 else int(year)
    hour_n = int(hour)
    if ampm:
        if not 1 <= hour_n <= 12:
            return None
        hour_n = hour_n % 12 + (12 if ampm.lower() == "p" else 0)
    try:
        return datetime(year_n, int(month), int(day), hour_n, int(minute), int(second or 0))
    except ValueError:
        return None


def _detect_date_order(headers: list[tuple]) -> tuple[str, bool]:
    """Return (order, ambiguous) for the date parts of every header line."""
    if sum(len(h[0]) == 4 for h in headers) > len(headers) / 2:
        return YEAR_FIRST, False

    day_first_votes = sum(int(h[0]) > 12 for h in headers)
    month_first_votes = sum(int(h[1]) > 12 for h in headers)
    if day_first_votes or month_first_votes:
        return (DAY_FIRST if day_first_votes >= month_first_votes else MONTH_FIRST), False

    # Every date fits both readings. A chat is exported oldest first, so the
    # reading with fewer backwards steps in time is the likelier one.
    def backwards_steps(order: str) -> int:
        stamps = [t for t in (_to_datetime(h, order) for h in headers) if t]
        return sum(later < earlier for earlier, later in zip(stamps, stamps[1:]))

    if backwards_steps(MONTH_FIRST) < backwards_steps(DAY_FIRST):
        return MONTH_FIRST, True
    return DAY_FIRST, True


def _classify(rest: str, marked: bool) -> tuple[str | None, str, str]:
    """Split what follows the timestamp into (sender, text, kind)."""
    if _SYSTEM.match(rest):
        return None, rest, SYSTEM

    if ": " in rest:
        sender, body = rest.split(": ", 1)
    elif rest.endswith(":"):
        sender, body = rest[:-1], ""
    else:
        # No "Name: " part at all, so it is a notice from WhatsApp itself.
        return None, rest, SYSTEM

    sender = sender.strip().lstrip("~").strip()
    body = body.strip()
    if marked and _SYSTEM.match(body):
        # iPhone attributes some notices to the group name or to a member.
        return None, body, SYSTEM
    if _DELETED.match(body):
        return sender, body, DELETED
    if _MEDIA.match(body) or (marked and _MEDIA_MARKED.match(body)):
        return sender, body, MEDIA
    return sender, body, TEXT


def parse_chat(text: str, date_order: str = "auto") -> ParseResult:
    """Parse the full text of an exported chat.

    date_order is "auto", "dmy" (day first) or "mdy" (month first). Year-first
    dates are recognised on their own and ignore this setting.
    """
    if date_order not in ("auto", DAY_FIRST, MONTH_FIRST):
        raise ValueError(f"date_order must be 'auto', 'dmy' or 'mdy', not {date_order!r}")

    lines = []
    for raw in text.splitlines():
        marked = "‎" in raw
        lines.append((_ODD_SPACES.sub(" ", _MARKS.sub("", raw)), marked))

    # The style that recognises more lines is the style of the file.
    counts = {style: sum(bool(rx.match(line)) for line, _ in lines) for style, rx in _HEADERS.items()}
    style = max(counts, key=counts.get)
    if counts[style] == 0:
        unparsed = sum(bool(line.strip()) for line, _ in lines)
        return ParseResult([], None, None, False, None, unparsed)
    header = _HEADERS[style]

    matches = [header.match(line) for line, _ in lines]
    groups = [m.groups() for m in matches if m]
    order, ambiguous = _detect_date_order(groups)
    if order != YEAR_FIRST and date_order != "auto":
        order, ambiguous = date_order, False

    messages: list[Message] = []
    current: list | None = None  # [timestamp, sender, text lines, kind]
    unparsed = 0
    uses_am_pm = False

    def close() -> None:
        if current is not None:
            stamp, sender, body, kind = current
            joined = _EDITED_TAG.sub("", "\n".join(body).strip())
            messages.append(Message(stamp, sender, joined, kind))

    for (line, marked), match in zip(lines, matches):
        stamp = _to_datetime(match.groups(), order) if match else None
        if stamp is None:
            # Not a message start: either a continuation line or stray text.
            if current is not None:
                current[2].append(line)
            elif line.strip():
                unparsed += 1
            continue
        close()
        uses_am_pm = uses_am_pm or bool(match.group(7))
        sender, body, kind = _classify(match.group(8) or "", marked)
        current = [stamp, sender, [body], kind]
    close()

    clock = ("12h" if uses_am_pm else "24h") if messages else None
    return ParseResult(messages, style, order, ambiguous, clock, unparsed)


def decode_export(data: bytes) -> str:
    """Decode the bytes of an exported chat. WhatsApp writes UTF-8."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig", errors="replace")


def load_export(data: bytes, filename: str = "") -> str:
    """Return the chat text from an uploaded .txt, or from the .zip iPhone exports.

    The zip is opened in memory. Nothing is extracted to disk.
    """
    if filename.lower().endswith(".zip") or data.startswith(b"PK\x03\x04"):
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise ValueError("This file is not a valid zip archive.") from exc
        with archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".txt")]
            if not names:
                raise ValueError("The zip archive does not contain a .txt chat file.")
            chat = next((n for n in names if Path(n).name == "_chat.txt"), names[0])
            data = archive.read(chat)
    return decode_export(data)


def parse_file(path: str | Path, date_order: str = "auto") -> ParseResult:
    """Parse an exported chat from a .txt or .zip file on disk."""
    path = Path(path)
    return parse_chat(load_export(path.read_bytes(), path.name), date_order)


def to_dataframe(messages: list[Message]) -> pd.DataFrame:
    """One row per message, with the columns in COLUMNS."""
    frame = pd.DataFrame(
        {
            "timestamp": pd.Series([m.timestamp for m in messages], dtype="datetime64[ns]"),
            "sender": pd.Series([m.sender for m in messages], dtype="object"),
            "text": pd.Series([m.text for m in messages], dtype="object"),
            "kind": pd.Series([m.kind for m in messages], dtype="object"),
        }
    )
    return frame[COLUMNS]
