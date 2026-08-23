import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtCore import QUrl
    from PyQt6.QtQuick import QQuickItem
    from PyQt6.QtQml import QQmlComponent, QQmlEngine
except ImportError:  # pragma: no cover - exercised only in minimal environments
    QGuiApplication = None
    QUrl = None
    QQuickItem = None
    QQmlComponent = None
    QQmlEngine = None


@unittest.skipUnless(QGuiApplication is not None, "PyQt6 is not installed")
class ChapterListQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.engine = QQmlEngine()
        source = Path(__file__).parents[1] / "gui/qml/components/ChapterList.qml"
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(source)))
        if self.component.isError():
            self.fail("Failed to load ChapterList.qml: " + " | ".join(
                error.toString() for error in self.component.errors()
            ))
        self.chapter_list = self.component.create()
        if self.chapter_list is None:
            self.fail("Failed to instantiate ChapterList.qml")

        self.chapters = [
            {"chapter_id": 101, "number": "1", "title": "One", "group_name": "A", "selected": False},
            {"chapter_id": 102, "number": "2", "title": "Two", "group_name": "B", "selected": False},
            {"chapter_id": 103, "number": "3", "title": "Three", "group_name": "A", "selected": False},
        ]
        self.chapter_list.setChapters(self.chapters)

    def tearDown(self):
        self.chapter_list.deleteLater()
        self.engine.deleteLater()
        self.qt_app.processEvents()

    def selected_ids(self):
        selected = self.chapter_list.getSelectedChapters().toVariant()
        return [chapter["chapter_id"] for chapter in selected]

    def counter_text(self):
        return next(
            item.property("text")
            for item in self.chapter_list.findChildren(QQuickItem)
            if item.metaObject().className() == "QQuickText"
            and str(item.property("text")).endswith(" selected")
        )

    def test_manual_selection_updates_count_and_download_payload(self):
        self.chapter_list.setChapterSelected(101, True)

        self.assertEqual(self.chapter_list.property("selectedCount"), 1)
        self.assertTrue(self.chapter_list.isChapterSelected(101))
        self.assertEqual(self.selected_ids(), [101])
        self.assertEqual(self.counter_text(), "1 selected")

    def test_filtered_bulk_selection_only_changes_visible_rows(self):
        self.chapter_list.applyFilter("A")
        self.chapter_list.setVisibleSelection(True)

        self.assertEqual(self.chapter_list.property("selectedCount"), 2)
        self.assertEqual(self.selected_ids(), [101, 103])
        self.assertFalse(self.chapter_list.isChapterSelected(102))

    def test_filter_changes_preserve_hidden_selection_and_none_is_visible_only(self):
        self.chapter_list.applyFilter("A")
        self.chapter_list.setVisibleSelection(True)
        self.chapter_list.applyFilter("B")
        self.chapter_list.setVisibleSelection(True)

        self.assertEqual(self.selected_ids(), [101, 102, 103])
        self.assertEqual(self.chapter_list.property("selectedCount"), 3)

        self.chapter_list.setVisibleSelection(False)

        self.assertEqual(self.selected_ids(), [101, 103])
        self.assertEqual(self.chapter_list.property("selectedCount"), 2)

    def test_reloading_chapters_resets_selection(self):
        self.chapter_list.setChapterSelected(101, True)
        self.chapter_list.setChapters([
            {"chapter_id": 201, "number": "1", "title": "New", "group_name": "C", "selected": False}
        ])

        self.assertEqual(self.chapter_list.property("selectedCount"), 0)
        self.assertEqual(self.selected_ids(), [])


if __name__ == "__main__":
    unittest.main()
