"""
Shared nodriver browser launch helpers.
"""

from typing import Any

from .logger import get_logger
from .nodriver_compat import load_nodriver


logger = get_logger(__name__)


_COMMON_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
]

_HEADLESS_WINDOW_SIZE = "1920,1080"


def get_browser_args(headless: bool, platform: str | None = None) -> list[str]:
    """Return Chrome args for nodriver's headful/headless launch modes.

    ``platform`` is retained for source compatibility with earlier callers;
    native headless mode is platform-independent and does not need window
    positioning tricks.
    """
    del platform
    browser_args = list(_COMMON_BROWSER_ARGS)

    if headless:
        browser_args.append(f"--window-size={_HEADLESS_WINDOW_SIZE}")
    else:
        browser_args.append("--start-maximized")

    return browser_args


def _is_headless_argument(argument: str) -> bool:
    return argument == "--headless" or argument.startswith("--headless=")


def _validate_effective_args(headless: bool, effective_args: list[str]) -> None:
    """Fail closed if nodriver does not produce the requested mode."""
    headless_args = [argument for argument in effective_args if _is_headless_argument(argument)]

    if headless:
        if "--headless=new" not in headless_args:
            raise RuntimeError(
                "Headless mode was requested, but nodriver did not produce --headless=new"
            )
        if "--start-maximized" in effective_args:
            raise RuntimeError("Headless mode must not include --start-maximized")
    elif headless_args:
        raise RuntimeError(
            "Headful mode was requested, but nodriver produced a headless switch"
        )


async def start_browser(headless: bool, nodriver: Any = None):
    """Start nodriver using the shared browser argument policy."""
    if not isinstance(headless, bool):
        raise TypeError(f"headless must be a bool, got {type(headless).__name__}")

    uc = nodriver if nodriver is not None else load_nodriver()
    browser_args = get_browser_args(headless)

    # Supplying an explicit Config lets us verify the final command line
    # before Chrome is spawned.  Keep the fallback for lightweight test doubles
    # and compatible nodriver facades that only expose ``start``.
    config_factory = getattr(uc, "Config", None)
    if config_factory is None:
        return await uc.start(headless=headless, browser_args=browser_args)

    config = config_factory(headless=headless, browser_args=browser_args)
    effective_args = list(config())
    _validate_effective_args(headless, effective_args)
    logger.debug(
        "Starting browser (headless=%s, executable=%s)",
        headless,
        getattr(config, "browser_executable_path", "unknown"),
    )

    return await uc.start(
        config=config,
        # Keep these explicit for compatibility with nodriver facades and
        # callers that inspect the launch request.
        headless=headless,
        browser_args=browser_args,
    )
