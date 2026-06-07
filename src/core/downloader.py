"""
Main downloader with threading support for concurrent downloads.
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Optional, Callable
from rich.progress import Progress, TaskID, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

import requests

from .models import MangaInfo, Chapter, DownloadConfig, OutputFormat
from ..api.comix import ComixAPI
from ..formats.images import save_images, cleanup_images
from ..formats.pdf import create_pdf
from ..formats.cbz import create_cbz
from ..utils.retry import RetryableDownloader
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Global event to signal cancellation across all downloaders
_cancel_event = threading.Event()

def cancel_downloads():
    """Signal all active downloaders to stop."""
    _cancel_event.set()
    logger.warning("Cancellation signal received. Stopping downloads...")

def is_cancelled():
    """Check if cancellation has been signaled."""
    return _cancel_event.is_set()

class ImageDownloader:
    """Downloads images with threading and retry logic."""
    
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.retrier = RetryableDownloader(
            max_retries=config.retry_count,
            base_delay=config.retry_delay
        )
    
    @staticmethod
    def _normalize_image(image: str | dict) -> tuple[str, bool, bytes | None]:
        if isinstance(image, dict):
            data = image.get("data")
            if data is not None and not isinstance(data, bytes):
                data = bytes(data)
            return image.get("url", ""), bool(image.get("scrambled")), data
        return image, False, None

    def download_image(self, image: str | dict, index: int) -> tuple[int, bytes | None, str | None]:
        """
        Download a single image with retry logic.
        
        Returns:
            Tuple of (index, image_bytes, error_message)
        """
        def _download():
            if is_cancelled():
                raise InterruptedError("Download cancelled")
                
            url, is_scrambled, decrypted_data = self._normalize_image(image)
            if decrypted_data is not None:
                logger.debug(f"Using pre-decrypted image data for image {index}: {url}")
                return decrypted_data

            if is_scrambled:
                raise ValueError(f"Scrambled image {index} was not decrypted before download")

            clean_url = url
            if not clean_url.startswith("http"):
                clean_url = "https://comix.to" + clean_url

            logger.debug(f"Starting download of image {index}: {clean_url}")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://comix.to/",
                "Sec-Ch-Ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "image",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site",
            }

            response = requests.get(clean_url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            content = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                if is_cancelled():
                    raise InterruptedError("Download cancelled")
                if chunk:
                    content.extend(chunk)
                
            return bytes(content)
        
        success, data, error = self.retrier.download_with_retry(
            _download,
            f"Image {index}"
        )
        
        return index, data if success else None, error
    
    def download_all_images(
        self,
        image_items: list[str | dict],
        progress: Optional[Progress] = None,
        task_id: Optional[TaskID] = None,
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> list[tuple[int, bytes]]:
        """
        Download all images concurrently.
        
        Returns:
            List of (index, image_bytes) tuples for successful downloads
        """
        results = []
        failed = []
        
        logger.info(f"Downloading {len(image_items)} images concurrently...")
        
        with ThreadPoolExecutor(max_workers=self.config.max_image_workers) as executor:
            futures = {
                executor.submit(self.download_image, image, idx): idx
                for idx, image in enumerate(image_items, 1)
            }
            
            for future in as_completed(futures):
                if is_cancelled():
                    break
                idx = futures[future]
                try:
                    index, data, error = future.result()
                    if data:
                        results.append((index, data))
                    else:
                        failed.append((index, error))
                        logger.error(f"Failed to download image {index}: {error}")
                except Exception as e:
                    failed.append((idx, str(e)))
                    logger.error(f"Exception downloading image {idx}: {e}")
                
                if progress and task_id:
                    progress.advance(task_id)
                
                if on_progress:
                    on_progress(len(results) + len(failed), len(image_items))
        
        if failed:
            logger.warning(f"{len(failed)} images failed to download")
        
        return sorted(results, key=lambda x: x[0])


class ChapterDownloader:
    """Downloads a single chapter with all its images."""
    
    def __init__(self, config: DownloadConfig, manga: MangaInfo):
        self.config = config
        self.manga = manga
        self.image_downloader = ImageDownloader(config)
    
    def download_chapter(
        self,
        chapter: Chapter,
        progress: Optional[Progress] = None,
        parent_task: Optional[TaskID] = None,
        on_image_progress: Optional[Callable[[int, int], None]] = None
    ) -> tuple[bool, str]:
        """
        Download a chapter and save in configured format.
        
        Returns:
            Tuple of (success, message)
        """
        manga_folder = self.manga.get_safe_title()
        chapter_folder = chapter.get_safe_folder_name()
        base_path = Path(self.config.download_path) / manga_folder
        
        try:
            # Fetch image metadata and any pre-decrypted encrypted pages.
            slug_or_id = self.manga.slug if self.manga.slug else self.manga.hash_id
            image_items = ComixAPI.get_chapter_images(slug_or_id, chapter.chapter_id, chapter.number)
            
            if not image_items:
                return False, f"No images found for {chapter.get_display_name()}"
            
            # Create task for image downloads
            task_id = None
            if progress:
                task_id = progress.add_task(
                    f"[cyan]  └─ {chapter.get_display_name()}",
                    total=len(image_items)
                )
            
            # Download all images
            image_data = self.image_downloader.download_all_images(
                image_items, progress, task_id, on_progress=on_image_progress
            )
            
            if not image_data:
                return False, f"Failed to download any images for {chapter.get_display_name()}"
            
            # Save in configured format
            if self.config.output_format == OutputFormat.IMAGES:
                save_images(image_data, base_path, chapter_folder)
                
            elif self.config.output_format == OutputFormat.PDF:
                if self.config.keep_images:
                    image_paths = save_images(image_data, base_path, chapter_folder)
                    pdf_path = base_path / f"{chapter_folder}.pdf"
                    create_pdf(image_paths, pdf_path, chapter.get_display_name())
                else:
                    from ..formats.pdf import create_pdf_from_bytes
                    pdf_path = base_path / f"{chapter_folder}.pdf"
                    create_pdf_from_bytes(image_data, pdf_path, chapter.get_display_name())
                    
            elif self.config.output_format == OutputFormat.CBZ:
                if self.config.keep_images:
                    image_paths = save_images(image_data, base_path, chapter_folder)
                    cbz_path = base_path / f"{chapter_folder}.cbz"
                    create_cbz(image_paths, cbz_path, self.manga, chapter)
                else:
                    from ..formats.cbz import create_cbz_from_bytes
                    cbz_path = base_path / f"{chapter_folder}.cbz"
                    create_cbz_from_bytes(image_data, cbz_path, self.manga, chapter)
            
            if progress and task_id:
                progress.update(task_id, completed=len(image_items))
            
            return True, f"Downloaded {chapter.get_display_name()} ({len(image_data)} pages)"
            
        except Exception as e:
            logger.error(f"Error downloading chapter {chapter.number}: {e}")
            return False, f"Error: {str(e)}"


class MangaDownloader:
    """Main downloader orchestrating concurrent chapter downloads."""
    
    def __init__(self, config: DownloadConfig):
        self.config = config
    
    def download_chapters(
        self,
        manga: MangaInfo,
        chapters: list[Chapter],
        progress: Progress,
        on_chapter_complete: Optional[Callable[[Chapter, bool, str], None]] = None
    ) -> tuple[int, int]:
        """
        Download multiple chapters concurrently.
        
        Returns:
            Tuple of (successful_count, failed_count)
        """
        successful = 0
        failed = 0
        
        chapter_downloader = ChapterDownloader(self.config, manga)
        
        # Create main progress task
        main_task = progress.add_task(
            f"[bold green]Downloading {manga.title}",
            total=len(chapters)
        )
        
        with ThreadPoolExecutor(max_workers=self.config.max_chapter_workers) as executor:
            futures = {
                executor.submit(
                    chapter_downloader.download_chapter,
                    chapter,
                    progress,
                    main_task
                ): chapter
                for chapter in chapters
            }
            
            for future in as_completed(futures):
                if is_cancelled():
                    break
                chapter = futures[future]
                try:
                    success, message = future.result()
                    if success:
                        successful += 1
                    else:
                        failed += 1
                    
                    if on_chapter_complete:
                        on_chapter_complete(chapter, success, message)
                        
                except Exception as e:
                    failed += 1
                    logger.error(f"Exception downloading chapter {chapter.number}: {e}")
                    if on_chapter_complete:
                        on_chapter_complete(chapter, False, str(e))
                
                progress.advance(main_task)
        
        return successful, failed
