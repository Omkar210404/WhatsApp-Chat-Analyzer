"""Parser tests. Every chat line here is invented for the test."""

import io
import zipfile
from datetime import datetime

import pytest

from whatsapp_analyzer.parser import (
    ANDROID,
    COLUMNS,
    DAY_FIRST,
    DELETED,
    IPHONE,
    MEDIA,
    MONTH_FIRST,
    SYSTEM,
    TEXT,
    YEAR_FIRST,
    load_export,
    parse_chat,
    parse_file,
)

LRM = "‎"  # the invisible mark iPhone puts before system and media text
NNBSP = " "  # the narrow no-break space newer exports put before AM/PM


def only(text, **kwargs):
    """Parse text that should hold exactly one message and return it."""
    messages = parse_chat(text, **kwargs).messages
    assert len(messages) == 1
    return messages[0]


# --- the four supported line shapes -----------------------------------------


def test_android_24_hour():
    result = parse_chat("25/12/2023, 21:15 - Mira: Happy holidays!")
    message = result.messages[0]
    assert message.timestamp == datetime(2023, 12, 25, 21, 15)
    assert (message.sender, message.text, message.kind) == ("Mira", "Happy holidays!", TEXT)
    assert (result.style, result.date_order, result.clock) == (ANDROID, DAY_FIRST, "24h")


def test_android_12_hour_month_first():
    result = parse_chat("12/25/23, 9:15 PM - Mira: Happy holidays!")
    message = result.messages[0]
    assert message.timestamp == datetime(2023, 12, 25, 21, 15)
    assert (message.sender, message.text) == ("Mira", "Happy holidays!")
    assert (result.style, result.date_order, result.clock) == (ANDROID, MONTH_FIRST, "12h")


def test_iphone_24_hour():
    result = parse_chat("[25/12/2023, 21:15:03] Mira: Happy holidays!")
    message = result.messages[0]
    assert message.timestamp == datetime(2023, 12, 25, 21, 15, 3)
    assert (message.sender, message.text, message.kind) == ("Mira", "Happy holidays!", TEXT)
    assert (result.style, result.date_order, result.clock) == (IPHONE, DAY_FIRST, "24h")


def test_iphone_12_hour_month_first():
    result = parse_chat("[12/25/23, 9:15:03 PM] Mira: Happy holidays!")
    message = result.messages[0]
    assert message.timestamp == datetime(2023, 12, 25, 21, 15, 3)
    assert (result.style, result.date_order, result.clock) == (IPHONE, MONTH_FIRST, "12h")


# --- time formats -----------------------------------------------------------


@pytest.mark.parametrize(
    "stamp, hour",
    [
        ("9:15 PM", 21),
        ("9:15 pm", 21),
        ("9:15 p.m.", 21),
        (f"9:15{NNBSP}PM", 21),
        ("9:15 PM", 21),
        ("9:15 AM", 9),
        ("12:15 AM", 0),
        ("12:15 PM", 12),
        ("09:15", 9),
        ("00:15", 0),
    ],
)
def test_time_variants(stamp, hour):
    message = only(f"25/12/2023, {stamp} - Mira: hi")
    assert (message.timestamp.hour, message.timestamp.minute) == (hour, 15)
    assert message.text == "hi"


@pytest.mark.parametrize("date", ["25/12/2023", "25.12.2023", "25-12-2023", "25/12/23"])
def test_date_separators_and_short_year(date):
    assert only(f"{date}, 21:15 - Mira: hi").timestamp == datetime(2023, 12, 25, 21, 15)


def test_year_first_date():
    result = parse_chat("2023-12-25, 21:15 - Mira: hi")
    assert result.messages[0].timestamp == datetime(2023, 12, 25, 21, 15)
    assert result.date_order == YEAR_FIRST


# --- day-first or month-first ----------------------------------------------


def test_one_clear_date_settles_the_whole_file():
    result = parse_chat("01/02/2023, 10:00 - Mira: a\n25/02/2023, 10:00 - Mira: b")
    assert result.date_order == DAY_FIRST
    assert result.date_order_ambiguous is False
    assert result.messages[0].timestamp == datetime(2023, 2, 1, 10, 0)


def test_ambiguous_dates_use_ascending_order():
    # Month first: 5 Jan, 6 Jan, 1 Feb (ascending).
    # Day first: 1 May, 1 Jun, 2 Jan (goes backwards), so month first wins.
    result = parse_chat("1/5/23, 10:00 - Mira: a\n1/6/23, 10:00 - Mira: b\n2/1/23, 10:00 - Mira: c")
    assert result.date_order == MONTH_FIRST
    assert result.date_order_ambiguous is True
    assert result.messages[2].timestamp == datetime(2023, 2, 1, 10, 0)


def test_ambiguous_dates_fall_back_to_day_first():
    result = parse_chat("01/02/2023, 10:00 - Mira: a")
    assert result.date_order == DAY_FIRST
    assert result.date_order_ambiguous is True
    assert result.messages[0].timestamp == datetime(2023, 2, 1, 10, 0)


def test_date_order_can_be_forced():
    message = only("01/02/2023, 10:00 - Mira: a", date_order=MONTH_FIRST)
    assert message.timestamp == datetime(2023, 1, 2, 10, 0)


def test_unknown_date_order_is_rejected():
    with pytest.raises(ValueError):
        parse_chat("01/02/2023, 10:00 - Mira: a", date_order="ydm")


# --- multi-line messages ----------------------------------------------------


def test_multi_line_message_android():
    result = parse_chat(
        "25/12/2023, 21:15 - Mira: Packing list:\n"
        "- boots\n"
        "\n"
        "2 litres of water\n"
        "25/12/2023, 21:16 - Bruno: ok"
    )
    assert len(result.messages) == 2
    assert result.messages[0].text == "Packing list:\n- boots\n\n2 litres of water"
    assert result.messages[1].text == "ok"
    assert result.unparsed_lines == 0


def test_multi_line_message_iphone():
    result = parse_chat("[25/12/2023, 21:15:03] Mira: line one\nline two\n[25/12/2023, 21:16:00] Bruno: ok")
    assert [m.text for m in result.messages] == ["line one\nline two", "ok"]


def test_line_with_an_impossible_date_is_a_continuation():
    result = parse_chat("25/12/2023, 21:15 - Mira: scores\n45/99/2023, 21:16 - not a message")
    assert len(result.messages) == 1
    assert result.messages[0].text.endswith("not a message")


def test_text_keeps_colons_and_dashes():
    message = only("25/12/2023, 21:15 - Mira: Plan: meet at 7 - bring snacks: nuts")
    assert message.sender == "Mira"
    assert message.text == "Plan: meet at 7 - bring snacks: nuts"


def test_empty_message_body():
    message = only("25/12/2023, 21:15 - Mira: ")
    assert (message.sender, message.text, message.kind) == ("Mira", "", TEXT)


# --- system messages --------------------------------------------------------


@pytest.mark.parametrize(
    "notice",
    [
        "Messages and calls are end-to-end encrypted. No one outside of this chat can read them.",
        'Mira created group "Hiking Club"',
        "Mira added Bruno",
        "Bruno left",
        "Chen joined using this group's invite link",
        'Mira changed the subject from "Hiking" to "Hiking: winter"',
        "Mira changed this group's icon",
        "Mira removed Bruno",
        "Some notice in a wording this parser has never seen",
    ],
)
def test_android_system_messages(notice):
    message = only(f"25/12/2023, 21:15 - {notice}")
    assert (message.sender, message.kind, message.text) == (None, SYSTEM, notice)


def test_iphone_system_message_without_sender():
    message = only(f"[25/12/2023, 21:15:03] {LRM}Bruno left")
    assert (message.sender, message.kind, message.text) == (None, SYSTEM, "Bruno left")


def test_iphone_system_message_attributed_to_the_group():
    message = only(f"[25/12/2023, 21:15:03] Hiking Club: {LRM}Messages and calls are end-to-end encrypted.")
    assert (message.sender, message.kind) == (None, SYSTEM)


def test_a_person_typing_a_system_phrase_is_still_a_message():
    for line in ("25/12/2023, 21:15 - Mira: Bruno left", "[25/12/2023, 21:15:03] Mira: I added sugar"):
        message = only(line)
        assert (message.sender, message.kind) == ("Mira", TEXT)


# --- media and deleted placeholders ----------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "25/12/2023, 21:15 - Mira: <Media omitted>",
        "25/12/2023, 21:15 - Mira: IMG-20231225-WA0001.jpg (file attached)",
        f"[25/12/2023, 21:15:03] Mira: {LRM}image omitted",
        f"[25/12/2023, 21:15:03] Mira: {LRM}sticker omitted",
        f"[25/12/2023, 21:15:03] Mira: {LRM}GIF omitted",
        f"[25/12/2023, 21:15:03] Mira: {LRM}<attached: 00000012-PHOTO-2023-12-25-21-15-03.jpg>",
        f"[25/12/2023, 21:15:03] Mira: route.pdf • {LRM}3 pages {LRM}document omitted",
    ],
)
def test_media_placeholders(line):
    message = only(line)
    assert (message.sender, message.kind) == ("Mira", MEDIA)


def test_talking_about_omitted_media_is_still_a_message():
    assert only("25/12/2023, 21:15 - Mira: the video was omitted").kind == TEXT


@pytest.mark.parametrize(
    "line",
    [
        "25/12/2023, 21:15 - Mira: This message was deleted",
        "25/12/2023, 21:15 - Mira: You deleted this message",
        f"[25/12/2023, 21:15:03] Mira: {LRM}This message was deleted.",
    ],
)
def test_deleted_placeholders(line):
    message = only(line)
    assert (message.sender, message.kind) == ("Mira", DELETED)


def test_edited_tag_is_removed():
    assert only("25/12/2023, 21:15 - Mira: see you at 7 <This message was edited>").text == "see you at 7"


# --- hidden characters, line endings, odd input -----------------------------


def test_bom_marks_and_crlf_are_handled():
    text = "﻿25/12/2023, 21:15 - Mira: one\r\n‎25/12/2023, 21:16 - ‪+00 0000 000000‬: two\r\n"
    result = parse_chat(text)
    assert [m.text for m in result.messages] == ["one", "two"]
    assert result.messages[1].sender == "+00 0000 000000"


def test_iphone_tilde_before_unsaved_contact_is_dropped():
    assert only(f"[25/12/2023, 21:15:03] ~{NNBSP}Mira: hi").sender == "Mira"


def test_empty_input():
    result = parse_chat("")
    assert result.messages == []
    assert (result.style, result.date_order, result.clock, result.unparsed_lines) == (None, None, None, 0)


def test_text_that_is_not_a_chat():
    result = parse_chat("Dear diary,\n\ntoday I went hiking.\n")
    assert result.messages == []
    assert result.style is None
    assert result.unparsed_lines == 2


def test_lines_before_the_first_message_are_counted():
    result = parse_chat("stray line\n25/12/2023, 21:15 - Mira: hi")
    assert len(result.messages) == 1
    assert result.unparsed_lines == 1


# --- files and data frames --------------------------------------------------


def test_to_dataframe_columns_and_types():
    frame = parse_chat("25/12/2023, 21:15 - Mira: hi\n25/12/2023, 21:16 - Bruno left").to_dataframe()
    assert list(frame.columns) == COLUMNS
    assert len(frame) == 2
    assert str(frame["timestamp"].dtype).startswith("datetime64")
    assert frame["kind"].tolist() == [TEXT, SYSTEM]
    assert frame["sender"].isna().tolist() == [False, True]


def test_empty_dataframe_has_the_same_columns():
    frame = parse_chat("").to_dataframe()
    assert list(frame.columns) == COLUMNS
    assert frame.empty


def test_parse_file_reads_txt_and_zip(tmp_path):
    chat = "[25/12/2023, 21:15:03] Mira: hi from a file ⛰️\n"
    txt = tmp_path / "chat.txt"
    txt.write_text(chat, encoding="utf-8")
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("notes.txt", "not the chat")
        z.writestr("_chat.txt", chat)

    for path in (txt, archive):
        result = parse_file(path)
        assert [m.text for m in result.messages] == ["hi from a file ⛰️"]


def test_zip_without_a_chat_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("photo.jpg", b"not a real photo")
    with pytest.raises(ValueError, match="does not contain"):
        load_export(buffer.getvalue(), "export.zip")


def test_broken_zip_is_rejected():
    with pytest.raises(ValueError, match="not a valid zip"):
        load_export(b"this is not a zip", "export.zip")
