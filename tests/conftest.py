"""Shared fixtures. All chat data used by the tests is synthetic."""

from pathlib import Path

import pytest

from whatsapp_analyzer.parser import parse_file

ROOT = Path(__file__).resolve().parent.parent
ANDROID_SAMPLE = ROOT / "examples" / "sample_chat_android.txt"
IPHONE_SAMPLE = ROOT / "examples" / "sample_chat_iphone.txt"


@pytest.fixture(scope="session")
def android_sample():
    return parse_file(ANDROID_SAMPLE)


@pytest.fixture(scope="session")
def iphone_sample():
    return parse_file(IPHONE_SAMPLE)


@pytest.fixture(scope="session")
def sample_frame(android_sample):
    return android_sample.to_dataframe()
