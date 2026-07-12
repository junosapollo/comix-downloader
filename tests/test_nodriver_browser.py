import asyncio
import unittest

from src.utils.nodriver_browser import get_browser_args, start_browser


class FakeNodriver:
    def __init__(self):
        self.start_kwargs = None
        self.browser = object()

    async def start(self, **kwargs):
        self.start_kwargs = kwargs
        return self.browser


class NodriverBrowserTests(unittest.TestCase):
    def test_windows_headless_hides_window_without_maximizing(self):
        args = get_browser_args(True, platform="win32")

        self.assertIn("--window-size=1920,1080", args)
        self.assertIn("--window-position=-10000,-10000", args)
        self.assertNotIn("--start-maximized", args)

    def test_non_windows_headless_uses_stable_viewport_without_offscreen_position(self):
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform):
                args = get_browser_args(True, platform=platform)

                self.assertIn("--window-size=1920,1080", args)
                self.assertNotIn("--window-position=-10000,-10000", args)
                self.assertNotIn("--start-maximized", args)

    def test_headful_launch_still_starts_maximized(self):
        args = get_browser_args(False, platform="win32")

        self.assertIn("--start-maximized", args)
        self.assertNotIn("--window-size=1920,1080", args)
        self.assertNotIn("--window-position=-10000,-10000", args)

    def test_start_browser_passes_shared_args_to_nodriver(self):
        fake_nodriver = FakeNodriver()

        browser = asyncio.run(start_browser(True, nodriver=fake_nodriver))

        self.assertIs(browser, fake_nodriver.browser)
        self.assertEqual(fake_nodriver.start_kwargs["headless"], True)
        self.assertEqual(
            fake_nodriver.start_kwargs["browser_args"],
            get_browser_args(True),
        )


if __name__ == "__main__":
    unittest.main()
