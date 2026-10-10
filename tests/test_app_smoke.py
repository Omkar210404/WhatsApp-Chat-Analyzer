"""Run the Streamlit app headlessly on synthetic chats and check what it shows."""

import io
import zipfile

import pytest
from conftest import ANDROID_SAMPLE, ROOT
from streamlit.testing.v1 import AppTest

from whatsapp_analyzer import analysis

TILES = ["Messages", "Words", "Media", "Links", "People", "Active days"]


def tiles(app: AppTest) -> dict[str, int]:
    return {metric.label: int(metric.value.replace(",", "")) for metric in app.metric}


def expected_tiles(stats: dict) -> dict[str, int]:
    keys = ["messages", "words", "media", "links", "people", "active_days"]
    return {label: stats[key] for label, key in zip(TILES, keys)}


@pytest.fixture
def app():
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()


@pytest.fixture
def sample_app(app):
    app.toggle(key="use_sample").set_value(True).run()
    assert not app.exception
    return app


def test_start_page_shows_the_privacy_note_and_no_data(app):
    assert not app.exception
    assert not app.metric
    notes = [box.value for box in app.info]
    assert len(app.main.info) == len(app.sidebar.info) == 1
    assert all("never uploaded, logged or saved to disk" in note for note in notes)


def test_sample_numbers_match_the_analysis_module(sample_app, sample_frame):
    assert tiles(sample_app) == expected_tiles(analysis.overall_stats(sample_frame))
    assert [tab.label for tab in sample_app.tabs] == ["Activity", "People", "Words and emojis"]
    assert any("synthetic sample chat" in box.value for box in sample_app.warning)
    assert len(sample_app.get("vega_lite_chart")) == 7


def test_person_filter(sample_app, sample_frame):
    sample_app.selectbox(key="person").set_value("Bruno").run()
    assert not sample_app.exception
    bruno = analysis.overall_stats(analysis.filter_sender(sample_frame, "Bruno"))
    assert tiles(sample_app) == expected_tiles(bruno)
    assert sample_app.subheader[0].value == "Only Bruno"


def test_iphone_sample_gives_the_same_numbers(sample_app, sample_frame):
    sample_app.radio(key="sample_style").set_value("iPhone style").run()
    assert not sample_app.exception
    assert tiles(sample_app) == expected_tiles(analysis.overall_stats(sample_frame))
    assert any("iPhone export" in caption.value for caption in sample_app.caption)


def test_options_custom_stopwords_and_word_cloud(sample_app):
    sample_app.text_area(key="custom_stopwords").set_value("saturday, loop").run()
    sample_app.slider(key="top_n").set_value(5).run()
    sample_app.checkbox(key="word_cloud").set_value(True).run()
    assert not sample_app.exception
    words = next(table.value for table in sample_app.dataframe if list(table.value.columns) == ["word", "count"])
    assert len(words) == 5
    assert not {"saturday", "loop"} & set(words["word"])
    assert any("2 of your own" in caption.value for caption in sample_app.caption)
    assert len(sample_app.get("image")) == 1


def test_uploading_a_txt_file(app, sample_frame):
    app.sidebar.file_uploader[0].upload("WhatsApp Chat with Hiking Club.txt", ANDROID_SAMPLE.read_bytes(), "text/plain").run()
    assert not app.exception
    assert tiles(app) == expected_tiles(analysis.overall_stats(sample_frame))
    assert not app.warning  # an upload is not labelled as the sample


def test_uploading_an_iphone_style_zip(app):
    chat = "[25/12/2023, 21:15:03] Mira: hello from a zip\n[25/12/2023, 21:16:00] Bruno: got it\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("_chat.txt", chat)
    app.sidebar.file_uploader[0].upload("export.zip", buffer.getvalue(), "application/zip").run()
    assert not app.exception
    assert tiles(app)["Messages"] == 2
    assert tiles(app)["People"] == 2


def test_ambiguous_dates_show_a_warning(app):
    app.sidebar.file_uploader[0].upload("chat.txt", b"01/02/2023, 10:00 - Mira: hi\n", "text/plain").run()
    assert not app.exception
    assert any("is a guess" in box.value for box in app.warning)


@pytest.mark.parametrize(
    "name, data, message",
    [
        ("diary.txt", b"Dear diary,\ntoday I went hiking.\n", "No WhatsApp messages were recognised"),
        ("empty.txt", b"", "No WhatsApp messages were recognised"),
        ("broken.zip", b"this is not a zip", "not a valid zip"),
    ],
)
def test_files_that_are_not_chats_get_a_clear_message(app, name, data, message):
    app.sidebar.file_uploader[0].upload(name, data, "application/octet-stream").run()
    assert not app.exception
    assert not app.metric
    assert any(message in box.value for box in app.error)
