import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtCore import QUrl
from PyQt6.QtQml import QQmlComponent, QQmlEngine

class ProgressPanelQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.engine = QQmlEngine()
        source = Path(__file__).parents[1] / "gui/qml/components/ProgressPanel.qml"
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(source)))
        self.panel = self.component.create()
        self.assertIsNotNone(self.panel, "Failed to load ProgressPanel.qml")

    def tearDown(self):
        self.panel.deleteLater()
        self.engine.deleteLater()
        self.qt_app.processEvents()

    def test_counters_and_status(self):
        self.panel.setChapterStatus("Chapter 1", True, "")
        self.assertEqual(self.panel.property("successCount"), 1)
        
        self.panel.setChapterStatus("Chapter 2", False, "Download cancelled")
        self.assertEqual(self.panel.property("cancelledCount"), 1)
        self.assertEqual(self.panel.property("failCount"), 0)
        
        self.panel.addFailure({"name": "Chapter 3", "chapter_id": 3, "number": "3", "reason": "Timeout", "category": "network", "message": "Connection timed out"})
        self.assertEqual(self.panel.property("failCount"), 1)
        
        self.panel.setChapterStatus("Chapter 3", False, "Connection timed out")
        self.assertEqual(self.panel.property("successCount"), 1)
        self.assertEqual(self.panel.property("cancelledCount"), 1)
        self.assertEqual(self.panel.property("failCount"), 1)

    def test_reset(self):
        self.panel.setChapterStatus("C1", True, "")
        self.panel.addFailure({"name": "C2", "chapter_id": 2, "number": "2", "reason": "Err", "category": "error", "message": "Err"})
        self.panel.reset()
        self.assertEqual(self.panel.property("successCount"), 0)
        self.assertEqual(self.panel.property("failCount"), 0)
        self.assertEqual(self.panel.property("viewFilter"), "all")
        self.assertEqual(self.panel.property("rowIndex").toVariant(), {})
        self.assertEqual(self.panel.property("failedIndex").toVariant(), {})

if __name__ == '__main__':
    unittest.main()
