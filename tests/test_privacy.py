"""Guards for the privacy promises in the README.

These are static checks on the source and the settings. They catch someone
adding a network call, a file write or a log line by accident. They are not a
proof, which is why the README also says how to check with the network off.
"""

import ast
import shutil
import subprocess
import tomllib

import pytest
from conftest import ROOT

SOURCES = sorted((ROOT / "whatsapp_analyzer").glob("*.py")) + [ROOT / "app.py"]

NETWORK_MODULES = {
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp",
    "ftplib", "smtplib", "telnetlib", "websocket", "websockets", "xmlrpc",
}  # fmt: skip
LOGGING_MODULES = {"logging", "syslog"}
WRITE_CALLS = {
    "open", "print", "write", "write_text", "write_bytes", "writelines", "dump",
    "to_csv", "to_excel", "to_json", "to_parquet", "to_pickle", "to_feather", "to_hdf", "to_sql",
}  # fmt: skip


def imported_modules(tree: ast.AST) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def called_names(tree: ast.AST) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            found.add(func.id if isinstance(func, ast.Name) else getattr(func, "attr", ""))
    return found


def test_there_is_source_to_check():
    names = {path.name for path in SOURCES}
    assert {"parser.py", "analysis.py", "text.py", "app.py"} <= names


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_network_or_logging_imports(path):
    modules = imported_modules(ast.parse(path.read_text(encoding="utf-8")))
    assert not modules & NETWORK_MODULES
    assert not modules & LOGGING_MODULES


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_nothing_is_written_or_printed(path):
    assert not called_names(ast.parse(path.read_text(encoding="utf-8"))) & WRITE_CALLS


def test_streamlit_telemetry_is_off_and_server_is_local_only():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["browser"]["gatherUsageStats"] is False
    assert config["server"]["address"] == "localhost"


def test_streamlit_theme_loads_no_web_fonts():
    assert "http" not in (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8").lower()


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs a git checkout")
def test_gitignore_blocks_chat_exports_but_not_the_samples():
    def ignored(name: str) -> bool:
        return subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT).returncode == 0

    for name in (
        "WhatsApp Chat with Someone.txt",
        "_chat.txt",
        "family.txt",
        "notes/chat.txt",
        "examples/my_real_chat.txt",
        "WhatsApp Chat - Someone.zip",
        "chats/export.csv",
        "private/anything",
    ):
        assert ignored(name), f"{name} would be committed"
    for name in (
        "requirements.txt",
        "examples/sample_chat_android.txt",
        "examples/sample_chat_iphone.txt",
        "whatsapp_analyzer/stopwords_en.txt",
    ):
        assert not ignored(name), f"{name} is ignored"
