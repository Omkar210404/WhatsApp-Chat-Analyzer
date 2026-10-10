"""The synthetic sample: it must parse cleanly in both export styles."""

from conftest import ANDROID_SAMPLE, IPHONE_SAMPLE

from scripts import generate_sample_chat as generator
from whatsapp_analyzer.parser import ANDROID, DAY_FIRST, DELETED, IPHONE, MEDIA, MONTH_FIRST, SYSTEM, TEXT


def test_android_sample_is_recognised(android_sample):
    assert (android_sample.style, android_sample.date_order, android_sample.clock) == (ANDROID, DAY_FIRST, "24h")
    assert android_sample.date_order_ambiguous is False
    assert android_sample.unparsed_lines == 0


def test_iphone_sample_is_recognised(iphone_sample):
    assert (iphone_sample.style, iphone_sample.date_order, iphone_sample.clock) == (IPHONE, MONTH_FIRST, "12h")
    assert iphone_sample.date_order_ambiguous is False
    assert iphone_sample.unparsed_lines == 0


def test_every_generated_event_becomes_one_message(android_sample, iphone_sample):
    events = generator.build_events()
    assert len(android_sample.messages) == len(events)
    assert len(iphone_sample.messages) == len(events)


def test_parsed_sample_matches_what_the_generator_wrote(android_sample):
    kinds = {"encryption": SYSTEM}
    for event, message in zip(generator.build_events(), android_sample.messages):
        assert message.kind == kinds.get(event.kind, event.kind)
        assert message.sender == event.sender
        assert message.timestamp == event.when.replace(second=0)
        if event.kind in ("text", "system", "encryption"):
            assert message.text == event.text


def test_both_styles_give_the_same_conversation(android_sample, iphone_sample):
    for android, iphone in zip(android_sample.messages, iphone_sample.messages):
        assert android.sender == iphone.sender
        assert android.kind == iphone.kind
        assert android.timestamp == iphone.timestamp.replace(second=0)
        if android.kind == TEXT:
            assert android.text == iphone.text


def test_sample_covers_every_case_the_parser_handles(android_sample):
    messages = android_sample.messages
    assert {m.kind for m in messages} == {TEXT, MEDIA, DELETED, SYSTEM}
    assert any("\n" in m.text for m in messages), "no multi-line message"
    assert any("https://example." in m.text for m in messages), "no link"
    assert not any("<This message was edited>" in m.text for m in messages)
    assert any(e.edited for e in generator.build_events()), "no edited message"
    assert all(m.sender is None for m in messages if m.kind == SYSTEM)
    assert all(m.sender for m in messages if m.kind != SYSTEM)


def test_sample_is_labelled_as_synthetic(android_sample):
    first = next(m for m in android_sample.messages if m.kind == TEXT)
    assert "synthetic sample" in first.text
    assert "invented" in first.text


def test_links_in_the_sample_use_reserved_example_domains(android_sample):
    for message in android_sample.messages:
        for word in message.text.split():
            if word.startswith("http"):
                assert word.startswith(("https://example.com/", "https://example.org/"))


def test_generator_reproduces_the_committed_files():
    events = generator.build_events()
    assert generator.render_android(events).encode("utf-8") == ANDROID_SAMPLE.read_bytes().replace(b"\r\n", b"\n")
    assert generator.render_iphone(events).encode("utf-8") == IPHONE_SAMPLE.read_bytes().replace(b"\r\n", b"\n")
