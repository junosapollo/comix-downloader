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
        self.evaluate_kwargs = None

    async def evaluate(self, script, **kwargs):
        self.script = script
        self.evaluate_kwargs = kwargs
        return self.result


class ComixChapterTests(unittest.TestCase):
    def test_normalizes_manga_summary_shape(self):
        summary = ComixAPI._normalize_manga_summary({
            "id": 42,
            "hid": "abc12",
            "title": "Example Manga",
            "type": "manhwa",
            "status": "releasing",
            "year": "2025",
            "latestChapter": 18,
            "ratedAvg": "8.7",
            "contentRating": "erotica",
            "poster": {"medium": "https://static.example/cover.jpg"},
            "url": "/title/abc12-example-manga",
        })

        self.assertEqual(summary.manga_id, 42)
        self.assertEqual(summary.manga_code, "abc12")
        self.assertEqual(summary.title, "Example Manga")
        self.assertEqual(summary.poster_url, "https://static.example/cover.jpg")
        self.assertEqual(summary.year, 2025)
        self.assertEqual(summary.latest_chapter, "18")
        self.assertEqual(summary.rated_avg, 8.7)
        self.assertEqual(summary.content_rating, "erotica")
        self.assertEqual(summary.canonical_url, "https://comix.to/title/abc12-example-manga")

    def test_normalizes_manga_summary_from_url_when_hash_is_missing(self):
        summary = ComixAPI._normalize_manga_summary({
            "title": "URL Only",
            "url": "https://comix.to/title/u77-url-only",
        })

        self.assertEqual(summary.manga_code, "u77")
        self.assertEqual(summary.canonical_url, "https://comix.to/title/u77-url-only")

    def test_rejects_manga_summary_without_identity(self):
        self.assertIsNone(ComixAPI._normalize_manga_summary({"title": "No URL"}))
        self.assertIsNone(ComixAPI._normalize_manga_summary({"hid": "abc"}))

    def test_normalizes_manga_browse_page_and_deduplicates(self):
        page = ComixAPI._normalize_manga_browse_page({
            "items": [
                {"hid": "a1", "title": "One", "url": "/title/a1-one"},
                {"hid": "a1", "title": "Duplicate", "url": "/title/a1-duplicate"},
                {"hid": "b2", "title": "Two", "url": "/title/b2-two"},
            ],
            "meta": {"page": 2, "lastPage": 5, "total": 41},
        }, requested_page=2)

        self.assertEqual([item.manga_code for item in page.items], ["a1", "b2"])
        self.assertEqual(page.page, 2)
        self.assertEqual(page.last_page, 5)
        self.assertEqual(page.total, 41)
        self.assertTrue(page.has_next)
        self.assertTrue(page.has_previous)

    def test_discovery_page_api_uses_current_client_and_all_ratings(self):
        page = FakePage(
            '{"ok":true,"data":{"items":['
            '{"hid":"a1","title":"One","url":"/title/a1-one"}'
            '],"meta":{"page":1,"lastPage":1,"total":1}}}'
        )

        result = asyncio.run(ComixAPI._fetch_discovery_via_page_api(
            page, keyword="one", page_number=2, limit=20
        ))

        self.assertTrue(result["ok"])
        self.assertIn("api.list", page.script)
        self.assertIn("relevance: 'desc'", page.script)
        self.assertIn("safe", page.script)
        self.assertIn("pornographic", page.script)
        self.assertIn('const pageNumber = 2', page.script)
        self.assertEqual(page.evaluate_kwargs, {"await_promise": True, "return_by_value": True})

    def test_discovery_page_api_reports_errors(self):
        page = FakePage('{"ok":false,"error":"catalog unavailable"}')

        with self.assertRaisesRegex(RuntimeError, "catalog unavailable"):
            asyncio.run(ComixAPI._fetch_discovery_via_page_api(page))

    def test_discovery_highlights_use_trending_and_latest_calls(self):
        page = FakePage(
            '{"ok":true,"trending":['
            '{"hid":"t1","title":"Trend","url":"/title/t1-trend"}],'
            '"latest":{"items":['
            '{"hid":"l1","title":"Latest","url":"/title/l1-latest"}]}}'
        )

        result = asyncio.run(ComixAPI._fetch_discovery_via_page_api(
            page, highlights=True, limit=8
        ))

        self.assertEqual(result["trending"][0]["title"], "Trend")
        self.assertIn("api.top", page.script)
        self.assertIn("days: 7", page.script)
        self.assertIn("chapter_updated_at: 'desc'", page.script)

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
        self.assertEqual(
            page.evaluate_kwargs,
            {"await_promise": True, "return_by_value": True},
        )

    def test_page_api_error_raises_useful_exception(self):
        page = FakePage('{"ok":false,"error":"Comix API module not found"}')

        with self.assertRaisesRegex(RuntimeError, "Comix API module not found"):
            asyncio.run(ComixAPI._fetch_chapters_via_page_api(page, "y86v"))

    def test_page_api_rejects_missing_serialized_result(self):
        page = FakePage(None)

        with self.assertRaisesRegex(RuntimeError, "no serialized result"):
            asyncio.run(ComixAPI._fetch_chapters_via_page_api(page, "y86v"))

    def test_page_api_rejects_invalid_json_result(self):
        page = FakePage("not-json")

        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            asyncio.run(ComixAPI._fetch_chapters_via_page_api(page, "y86v"))


if __name__ == "__main__":
    unittest.main()
