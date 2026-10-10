"""Take the README screenshots from the running app, using the synthetic sample only.

This is a developer tool, not part of the app. It needs Playwright and an
installed Google Chrome:

    pip install playwright==1.63.0
    python scripts/capture_screenshots.py

It starts the app on a free local port, opens it in headless Chrome, switches
on the synthetic sample chat and saves the pictures to docs/screenshots/.

While the pages load it records the host of every request the browser makes.
If any request goes anywhere other than this machine, the script fails.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
WIDTH = 1400


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until_listening(port: int, seconds: int = 60) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise RuntimeError("the app did not start")


def settle(page: Page) -> None:
    """Wait for Streamlit to finish its run and for the charts to draw."""
    page.wait_for_selector("[data-testid='stStatusWidget']", state="detached", timeout=30_000)
    page.wait_for_timeout(2000)


def save(page: Page, name: str, full_height: bool = True) -> None:
    page.set_viewport_size({"width": WIDTH, "height": 900})
    settle(page)
    if full_height:
        # Streamlit scrolls inside its own container, so grow the window to fit.
        # Measured twice, because charts and images change the height as they load.
        for _ in range(2):
            height = page.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollHeight") + 20
            page.set_viewport_size({"width": WIDTH, "height": height})
            settle(page)
    page.screenshot(path=OUT / name)
    print(f"saved docs/screenshots/{name}")


def capture(page: Page, url: str) -> None:
    sidebar = page.get_by_test_id("stSidebar")

    page.goto(url, wait_until="networkidle")
    settle(page)
    save(page, "01-start.png", full_height=False)

    sidebar.get_by_text("Use the synthetic sample chat").click()
    page.wait_for_selector("[data-testid='stMetric']")
    save(page, "02-activity.png")

    page.get_by_role("tab", name="People").click()
    save(page, "03-people.png")

    sidebar.get_by_text("Options").click()
    sidebar.get_by_text("Show a word cloud").click()
    settle(page)
    page.get_by_role("tab", name="Words and emojis").click()
    save(page, "04-words.png")

    # One person only, back on the first tab.
    sidebar.get_by_text("Options").click()
    sidebar.locator("[data-testid='stSelectbox']").first.click()
    page.get_by_role("option", name="Bruno").click()
    settle(page)
    page.get_by_role("tab", name="Activity").click()
    save(page, "05-one-person.png", full_height=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    port = free_port()
    command = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true", "--server.port", str(port)]
    server = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    hosts: set[str] = set()
    try:
        wait_until_listening(port)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": WIDTH, "height": 900})
            # data: and blob: URLs have no host and never leave the browser.
            page.on("request", lambda request: hosts.add(urlparse(request.url).hostname or ""))
            capture(page, f"http://localhost:{port}")
            browser.close()
    finally:
        server.terminate()

    hosts.discard("")
    print(f"hosts the browser contacted: {sorted(hosts)}")
    outside = hosts - LOCAL_HOSTS
    if outside:
        sys.exit(f"FAILED: the page made requests to {sorted(outside)}")
    print("OK: every request stayed on this machine")


if __name__ == "__main__":
    main()
