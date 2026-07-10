import asyncio
import importlib
import sys
import types
import unittest


def load_comix_api():
    requests_stub = types.ModuleType("requests")

    class Session:
        def __init__(self):
            self.headers = {}

        def get(self, *args, **kwargs):
            raise AssertionError("requests.Session.get should not be called by these tests")

    requests_stub.Session = Session
    requests_stub.exceptions = types.SimpleNamespace(RequestException=Exception)
    sys.modules.setdefault("requests", requests_stub)

    module = importlib.import_module("src.api.comix")
    return module.ComixAPI


ComixAPI = load_comix_api()


class FakePage:
    def __init__(self, result):
        self.result = result
        self.script = None

    async def evaluate(self, script):
        self.script = script
        return self.result


class ComixChapterTests(unittest.TestCase):
    def test_normalizes_current_chapter_api_shape(self):
        row = ComixAPI._normalize_chapter_api_item({
            "id": "9744989",
            "number": 100,
            "name": "Finale",
            "volume": 2,
            "group": {"id": 9897, "name": "Official"},
            "pagesCount": 42,
        })

        self.assertEqual(row["chapter_id"], 9744989)
        self.assertEqual(row["number"], "100")
        self.assertEqual(row["title"], "Finale")
        self.assertEqual(row["volume"], 2)
        self.assertEqual(row["group_name"], "Official")
        self.assertEqual(row["pages_count"], 42)

    def test_normalizes_legacy_chapter_api_shape(self):
        row = ComixAPI._normalize_chapter_api_item({
            "chapter_id": 1537020,
            "number": "1",
            "title": "Start",
            "scanlation_group": {"name": "MagusManga"},
            "pages_count": 18,
            "votes": 7,
        })

        self.assertEqual(row["chapter_id"], 1537020)
        self.assertEqual(row["title"], "Start")
        self.assertEqual(row["group_name"], "MagusManga")
        self.assertEqual(row["pages_count"], 18)
        self.assertEqual(row["votes"], 7)

    def test_uses_official_group_when_api_has_no_group_name(self):
        row = ComixAPI._normalize_chapter_api_item({
            "id": 1,
            "number": "12",
            "isOfficial": True,
        })

        self.assertEqual(row["group_name"], "Official")

    def test_rejects_api_items_without_required_identity(self):
        self.assertIsNone(ComixAPI._normalize_chapter_api_item({"id": 1}))
        self.assertIsNone(ComixAPI._normalize_chapter_api_item({"number": "1"}))
        self.assertIsNone(ComixAPI._normalize_chapter_api_item({"id": "bad", "number": "1"}))

    def test_normalizes_dom_row(self):
        row = ComixAPI._normalize_chapter_dom_row({
            "href": "/title/y86v-i-became-a-level-999-demon-queen/1537020-chapter-1",
            "title": "Opening",
            "group": "",
            "group_official": True,
        })

        self.assertEqual(row["chapter_id"], 1537020)
        self.assertEqual(row["number"], "1")
        self.assertEqual(row["title"], "Opening")
        self.assertEqual(row["group_name"], "Official")

    def test_dedupes_chapter_rows_by_id(self):
        rows = ComixAPI._dedupe_chapter_rows([
            {"chapter_id": 1, "number": "1"},
            {"chapter_id": 1, "number": "1 duplicate"},
            {"chapter_id": 2, "number": "2"},
        ])

        self.assertEqual(rows, [
            {"chapter_id": 1, "number": "1"},
            {"chapter_id": 2, "number": "2"},
        ])

    def test_page_api_result_is_normalized_and_deduped(self):
        page = FakePage(
            '{"ok":true,"items":['
            '{"id":2,"number":"2","name":"Two","group":{"name":"A"}},'
            '{"id":2,"number":"2","name":"Two again","group":{"name":"A"}},'
            '{"id":1,"number":"1","isOfficial":true}'
            ']}'
        )

        rows = asyncio.run(ComixAPI._fetch_chapters_via_page_api(page, "y86v"))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["chapter_id"], 2)
        self.assertEqual(rows[0]["title"], "Two")
        self.assertEqual(rows[1]["chapter_id"], 1)
        self.assertEqual(rows[1]["group_name"], "Official")
        self.assertIn("api.chapters", page.script)
        self.assertIn("order: { number: 'desc' }", page.script)

    def test_page_api_error_raises_useful_exception(self):
        page = FakePage('{"ok":false,"error":"Comix API module not found"}')

        with self.assertRaisesRegex(RuntimeError, "Comix API module not found"):
            asyncio.run(ComixAPI._fetch_chapters_via_page_api(page, "y86v"))


if __name__ == "__main__":
    unittest.main()
