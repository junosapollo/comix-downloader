import unittest
from src.core.failures import classify_failure, format_chapter_numbers, is_cancellation

class TestFailures(unittest.TestCase):
    def test_classify_failure(self):
        self.assertEqual(classify_failure("Download cancelled")[0], "cancelled")
        self.assertEqual(classify_failure("Incomplete image extraction for Chapter 1")[0], "extraction")
        self.assertEqual(classify_failure("Incomplete download for Chapter 1")[0], "partial")
        self.assertEqual(classify_failure("Failed to download any images")[0], "no_images")
        self.assertEqual(classify_failure("Cloudflare challenge failed")[0], "cloudflare")
        self.assertEqual(classify_failure("Connection timed out")[0], "network")
        self.assertEqual(classify_failure("Unknown error")[0], "error")
        self.assertEqual(classify_failure(None)[0], "error")

    def test_is_cancellation(self):
        self.assertTrue(is_cancellation("Download cancelled"))
        self.assertFalse(is_cancellation("Connection timeout"))

    def test_format_chapter_numbers(self):
        self.assertEqual(format_chapter_numbers(["1", "2", "3"]), "1–3")
        self.assertEqual(format_chapter_numbers(["1", "3", "4", "5", "8"]), "1, 3–5, 8")
        self.assertEqual(format_chapter_numbers(["3", "1", "2", "1"]), "1–3")
        self.assertEqual(format_chapter_numbers([1, 2, "2.5", 3]), "1–2, 2.5, 3")
        self.assertEqual(format_chapter_numbers(["1"] * 70, limit=60), "1")
        self.assertEqual(format_chapter_numbers([str(i) for i in range(1, 62)], limit=60), "1–61")
        
        # Test large sets and limit
        nums = [str(i) for i in range(1, 100, 2)] # 1, 3, 5... (no ranges)
        formatted = format_chapter_numbers(nums, limit=5)
        self.assertEqual(formatted, "1, 3, 5, 7, 9, +45 more")

if __name__ == '__main__':
    unittest.main()
