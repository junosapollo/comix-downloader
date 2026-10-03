"""
Download Bridge - Handles download operations between Python and QML
"""

import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, Property
from PyQt6.QtGui import QGuiApplication
import threading

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.core.failures import classify_failure, format_chapter_numbers, CANCELLED



class DownloadWorker(QThread):
    """Background worker for downloading chapters concurrently."""
    
    chapterProgress = pyqtSignal(str, int, int)  # chapter_name, current, total
    chapterComplete = pyqtSignal(str, bool, str)  # chapter_name, success, message
    chapterFailed = pyqtSignal('QVariant')         # structured failure payload

    overallProgress = pyqtSignal(int, int)  # completed, total
    finished = pyqtSignal(int, int)  # successful, failed
    error = pyqtSignal(str)
    
    def __init__(self, manga_dict: dict, chapters: list, config):
        super().__init__()
        self.manga_dict = manga_dict
        self.chapters = chapters
        self.config = config
        self._lock = threading.Lock()
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._failed_chapters = []

    
    def _download_single_chapter(self, chapter_dict, manga, total):
        """Download a single chapter. Called from thread pool."""
        try:
            from src.core.downloader import ChapterDownloader
            from src.core.models import Chapter
            
            # Convert dict to Chapter object
            chapter = Chapter(
                chapter_id=chapter_dict["chapter_id"],
                number=chapter_dict["number"],
                title=chapter_dict.get("title"),
                volume=chapter_dict.get("volume"),
                votes=chapter_dict.get("votes"),
                group_name=chapter_dict.get("group_name"),
                pages_count=chapter_dict.get("pages_count", 0)
            )
            
            # Build the display name before anything can raise
            chapter_name = chapter.get_display_name()

            
            # Create a callback for image progress
            def on_image_progress(current, total):
                self.chapterProgress.emit(chapter_name, current, total)
            
            # Download the chapter
            ch_downloader = ChapterDownloader(
                self.config,
                manga,
                reader_service=getattr(self, "_reader_service", None),
                image_pool=getattr(self, "_image_pool", None),
            )
            success, message = ch_downloader.download_chapter(
                chapter, 
                on_image_progress=on_image_progress
            )
            
            # Update progress with thread safety
            with self._lock:
                self._completed += 1
                if success:
                    self._successful += 1
                else:
                    self._failed += 1
                completed = self._completed
                successful = self._successful
                failed = self._failed
            
            # Emit signals (Qt handles thread safety for signals)
            self.chapterComplete.emit(chapter_name, success, message)
            if not success:
                self._record_failure(chapter_dict, chapter_name, message)
            self.overallProgress.emit(completed, total)
            
            return success, chapter_name
            
        except Exception as e:
            with self._lock:
                self._completed += 1
                self._failed += 1
                completed = self._completed
            
            self.chapterComplete.emit(chapter_name, False, str(e))
            self._record_failure(chapter_dict, chapter_name, str(e))
            self.overallProgress.emit(completed, total)
            return False, chapter_name
            
    def _record_failure(self, chapter_dict, name, message):
        category, label = classify_failure(message)
        if category == CANCELLED:
            return
        payload = {
            "name": name,
            "chapter_id": chapter_dict.get("chapter_id"),
            "number": str(chapter_dict.get("number", "?")),
            "group_name": chapter_dict.get("group_name") or "",
            "category": category,
            "reason": label,
            "message": message or "Failed",
        }
        with self._lock:
            self._failed_chapters.append(dict(chapter_dict))
        self.chapterFailed.emit(payload)

    
    def run(self):
        try:
            from src.core.models import MangaInfo
            from src.core.downloader import reset_downloads, ImageDownloadPool
            from src.api.comix import ChapterReaderService

            reset_downloads()
            
            # Convert dict back to MangaInfo
            manga = MangaInfo(
                manga_id=self.manga_dict.get("manga_id"),
                hash_id=self.manga_dict.get("hash_id"),
                title=self.manga_dict.get("title", "Unknown"),
                alt_titles=self.manga_dict.get("alt_titles", []),
                rank=self.manga_dict.get("rank"),
                manga_type=self.manga_dict.get("manga_type"),
                status=self.manga_dict.get("status"),
                poster_url=self.manga_dict.get("poster_url"),
                original_language=self.manga_dict.get("original_language"),
                final_chapter=self.manga_dict.get("final_chapter"),
                latest_chapter=self.manga_dict.get("latest_chapter"),
                start_date=self.manga_dict.get("start_date"),
                end_date=self.manga_dict.get("end_date"),
                year=self.manga_dict.get("year"),
                rated_avg=self.manga_dict.get("rated_avg"),
                rated_count=self.manga_dict.get("rated_count"),
                follows_total=self.manga_dict.get("follows_total"),
                is_nsfw=self.manga_dict.get("is_nsfw", False),
                slug=self.manga_dict.get("slug"),
                genres=self.manga_dict.get("genres", []),
                description=self.manga_dict.get("description", "")
            )
            
            total = len(self.chapters)
            max_workers = self.config.max_chapter_workers

            self._reader_service = ChapterReaderService(self.config.headless)
            self._image_pool = ImageDownloadPool(self.config.max_image_workers)
            
            # Use ThreadPoolExecutor for concurrent downloads
            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [
                        executor.submit(self._download_single_chapter, ch, manga, total)
                        for ch in self.chapters
                    ]

                    # Wait for all to complete
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception:
                            pass  # Errors are emitted by _download_single_chapter
            finally:
                self._image_pool.shutdown()
                self._reader_service.close()
                self._image_pool = None
                self._reader_service = None
            
            self.finished.emit(self._successful, self._failed)
            
        except Exception as e:
            self.error.emit(str(e))


class DownloadBridge(QObject):
    """Bridge for download operations exposed to QML."""
    
    downloadStarted = pyqtSignal()
    chapterProgress = pyqtSignal(str, int, int)
    chapterComplete = pyqtSignal(str, bool, str)
    chapterFailed = pyqtSignal('QVariant')
    overallProgress = pyqtSignal(int, int)
    downloadFinished = pyqtSignal(int, int)
    errorOccurred = pyqtSignal(str)
    hasFailuresChanged = pyqtSignal()

    
    def __init__(self, parent=None, config_manager=None):
        super().__init__(parent)
        self._worker = None
        self._last_manga = None
        self._last_config = None
        self._last_failed = []
        # Import here to avoid circular imports
        if config_manager is None:
            from src.utils.config import ConfigManager

            config_manager = ConfigManager()
        self._config_manager = config_manager

    
    @pyqtSlot('QVariant', 'QVariant', str, str)
    def startDownload(self, manga: dict, chapters, format_type: str, scanlator: str):
        """
        Start downloading selected chapters concurrently.
        
        Args:
            manga: Manga info dict
            chapters: List of selected chapter dicts (QJSValue from QML)
            format_type: Output format (images/pdf/cbz)
            scanlator: Preferred scanlator or empty for any
        """
        # Convert QJSValue to Python list
        if hasattr(chapters, 'toVariant'):
            chapters = chapters.toVariant()
        if not isinstance(chapters, list):
            chapters = list(chapters) if chapters else []
        
        if not chapters:
            self.errorOccurred.emit("No chapters selected")
            return
        
        # Import here to avoid circular imports
        from src.core.models import OutputFormat
        
        # Get config and update format
        config = self._config_manager.get_download_config()
        try:
            config.output_format = OutputFormat(format_type)
        except ValueError:
            self.errorOccurred.emit("Invalid format. Choose images, pdf, or cbz")
            return
        
        # Filter by scanlator preference if specified
        if scanlator and scanlator != "Any":
            filtered = []
            seen_numbers = set()
            # Prioritize chapters from preferred scanlator
            for ch in chapters:
                if ch.get("group_name") == scanlator and ch["number"] not in seen_numbers:
                    filtered.append(ch)
                    seen_numbers.add(ch["number"])
            # Add remaining chapters for numbers not covered
            for ch in chapters:
                if ch["number"] not in seen_numbers:
                    filtered.append(ch)
                    seen_numbers.add(ch["number"])
            chapters = filtered
        else:
            # Get unique chapters by number
            seen = set()
            unique = []
            for ch in chapters:
                if ch["number"] not in seen:
                    unique.append(ch)
                    seen.add(ch["number"])
            chapters = unique
        
        self.downloadStarted.emit()
        
        self._last_manga = manga
        self._last_config = config
        self._last_failed = []
        self.hasFailuresChanged.emit()

        # Create and start worker with concurrent downloads
        self._worker = DownloadWorker(manga, chapters, config)
        self._worker.chapterProgress.connect(self.chapterProgress.emit)
        self._worker.chapterComplete.connect(self.chapterComplete.emit)
        self._worker.chapterFailed.connect(self.chapterFailed.emit)
        self._worker.overallProgress.connect(self.overallProgress.emit)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self.errorOccurred.emit)
        self._worker.start()
    
    def _on_worker_finished(self, successful, failed):
        if self._worker:
            self._last_failed = self._worker._failed_chapters
            self.hasFailuresChanged.emit()
        self.downloadFinished.emit(successful, failed)

    @pyqtSlot()
    def cancelDownload(self):
        """Cancel the current download."""
        if self._worker and self._worker.isRunning():
            from src.core.downloader import cancel_downloads
            cancel_downloads()

    @pyqtSlot(result=bool)
    def hasFailures(self):
        return len(self._last_failed) > 0
    hasFailures = Property(bool, fget=hasFailures, notify=hasFailuresChanged)

    @pyqtSlot()
    def retryFailed(self):
        """Retry the failed chapters from the last download."""
        if self._worker and self._worker.isRunning():
            self.errorOccurred.emit("A download is already in progress")
            return
        if not self._last_failed:
            self.errorOccurred.emit("No failed chapters to retry")
            return
        
        self.downloadStarted.emit()
        self._last_failed = []
        self.hasFailuresChanged.emit()

        self._worker = DownloadWorker(self._last_manga, self._last_failed, self._last_config)
        self._worker.chapterProgress.connect(self.chapterProgress.emit)
        self._worker.chapterComplete.connect(self.chapterComplete.emit)
        self._worker.chapterFailed.connect(self.chapterFailed.emit)
        self._worker.overallProgress.connect(self.overallProgress.emit)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self.errorOccurred.emit)
        self._worker.start()

    @pyqtSlot('QVariant', result=str)
    def formatChapterNumbers(self, numbers):
        if hasattr(numbers, 'toVariant'):
            numbers = numbers.toVariant()
        return format_chapter_numbers(numbers)

    @pyqtSlot(str)
    def copyToClipboard(self, text):
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
