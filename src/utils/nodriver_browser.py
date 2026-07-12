"""
Shared nodriver browser launch helpers.
"""

import sys
from typing import Any

from .nodriver_compat import load_nodriver


_COMMON_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
]

_HEADLESS_WINDOW_SIZE = "1920,1080"
_WINDOWS_HEADLESS_POSITION = "-10000,-10000"


def get_browser_args(headless: bool, platform: str | None = None) -> list[str]:
    """Return Chrome args for nodriver, keeping headless windows hidden."""
    browser_args = list(_COMMON_BROWSER_ARGS)
    platform = platform or sys.platform

    if headless:
        browser_args.append(f"--window-size={_HEADLESS_WINDOW_SIZE}")
        if platform.startswith("win"):
            browser_args.append(f"--window-position={_WINDOWS_HEADLESS_POSITION}")
    else:
        browser_args.append("--start-maximized")

    return browser_args


async def start_browser(headless: bool, nodriver: Any = None):
    """Start nodriver using the shared browser argument policy."""
    uc = nodriver if nodriver is not None else load_nodriver()
    return await uc.start(
        headless=headless,
        browser_args=get_browser_args(headless),
    )
