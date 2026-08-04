import asyncio
import unittest

from src.utils.nodriver_browser import get_browser_args, start_browser


class FakeNodriver:
    class Config:
        def __init__(self, *, headless, browser_args):
            self.headless = headless
            self.browser_args = list(browser_args)
            self.browser_executable_path = "fake-browser"

        def __call__(self):
            args = list(self.browser_args)
            if self.headless:
                args.append("--headless=new")
            return args

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
        self.assertNotIn("--start-maximized", args)
        self.assertFalse(any(arg.startswith("--window-position=") for arg in args))

    def test_non_windows_headless_uses_stable_viewport_without_offscreen_position(self):
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform):
                args = get_browser_args(True, platform=platform)

                self.assertIn("--window-size=1920,1080", args)
                self.assertNotIn("--start-maximized", args)
                self.assertFalse(any(arg.startswith("--window-position=") for arg in args))

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
        self.assertEqual(
            fake_nodriver.start_kwargs["config"](),
            get_browser_args(True) + ["--headless=new"],
        )

    def test_headful_effective_config_has_no_headless_switch(self):
        fake_nodriver = FakeNodriver()

        asyncio.run(start_browser(False, nodriver=fake_nodriver))

        effective_args = fake_nodriver.start_kwargs["config"]()
        self.assertIn("--start-maximized", effective_args)
        self.assertFalse(any(arg.startswith("--headless") for arg in effective_args))

    def test_start_browser_fails_closed_when_headless_switch_is_missing(self):
        class BrokenConfig(FakeNodriver.Config):
            def __call__(self):
                return list(self.browser_args)

        class BrokenNodriver(FakeNodriver):
            Config = BrokenConfig

            def __init__(self):
                super().__init__()
                self.started = False

            async def start(self, **kwargs):
                self.started = True
                return await super().start(**kwargs)

        fake_nodriver = BrokenNodriver()
        with self.assertRaisesRegex(RuntimeError, "--headless=new"):
            asyncio.run(start_browser(True, nodriver=fake_nodriver))
        self.assertFalse(fake_nodriver.started)


if __name__ == "__main__":
    unittest.main()
