"""
Comix.to API wrapper for manga information and chapter data.
"""

import requests
from typing import Optional
from ..core.models import MangaInfo, Chapter
from ..utils.retry import retry_with_backoff
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ComixAPI:
    """API wrapper for comix.to"""
    
    BASE_URL = "https://comix.to/api/v2"
    
    @staticmethod
    def extract_manga_code(url: str) -> str:
        """
        Extract manga code from the title URL.
        Example: https://comix.to/title/93q1r-the-summoner -> 93q1r
        """
        parts = url.rstrip("/").split("/")
        last = parts[-1] if parts[-1] else parts[-2]
        code = last.split("-")[0]
        logger.debug(f"Extracted manga code: {code} from URL: {url}")
        return code
    
    @classmethod
    @retry_with_backoff()
    def get_manga_info(cls, manga_code: str) -> Optional[MangaInfo]:
        """Fetch manga information from API."""
        url = f"{cls.BASE_URL}/manga/{manga_code}/"
        logger.debug(f"Fetching manga info from: {url}")
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()["result"]
        
        return MangaInfo(
            manga_id=data.get("manga_id"),
            hash_id=data.get("hash_id"),
            title=data.get("title", "Unknown"),
            alt_titles=data.get("alt_titles", []),
            slug=data.get("slug"),
            rank=data.get("rank"),
            manga_type=data.get("type"),
            poster_url=data.get("poster", {}).get("large") or data.get("poster", {}).get("medium"),
            original_language=data.get("original_language"),
            status=data.get("status"),
            final_chapter=data.get("final_chapter"),
            latest_chapter=data.get("latest_chapter"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            rated_avg=data.get("rated_avg"),
            rated_count=data.get("rated_count"),
            follows_total=data.get("follows_total"),
            is_nsfw=data.get("is_nsfw", False),
            year=data.get("year"),
            genres=data.get("term_ids", []),
            description=data.get("synopsis", "")
        )
    
    @classmethod
    @retry_with_backoff()
    def get_all_chapters(cls, manga_code: str) -> list[Chapter]:
        """Fetch all chapters for a manga."""
        chapters = []
        page = 1
        
        while True:
            url = f"{cls.BASE_URL}/manga/{manga_code}/chapters?limit=100&page={page}&order[number]=asc"
            logger.debug(f"Fetching chapters page {page}")
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()["result"]
            items = data.get("items", [])
            
            if not items:
                break
            
            for chap in items:
                group = chap.get("scanlation_group")
                is_official = chap.get("is_official", 0)
                
                # Determine group name: prefer scanlation_group, then check is_official
                if group:
                    group_name = group["name"]
                elif is_official:
                    group_name = "Official"
                else:
                    group_name = None
                
                chapters.append(Chapter(
                    chapter_id=chap["chapter_id"],
                    number=chap["number"],
                    title=chap.get("name") or chap.get("title"),  # API uses 'name' field
                    volume=chap.get("volume"),
                    votes=chap.get("votes"),
                    group_name=group_name,
                    pages_count=chap.get("pages_count", 0)
                ))
            page += 1
        
        logger.info(f"Found {len(chapters)} chapters")
        return chapters
    
    @classmethod
    @retry_with_backoff()
    def get_chapter_images(cls, chapter_id: int) -> list[str]:
        """Fetch all image URLs for a chapter."""
        url = f"{cls.BASE_URL}/chapters/{chapter_id}/"
        logger.debug(f"Fetching images for chapter {chapter_id}")
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        images = data.get("result", {}).get("images", [])
        image_urls = [img["url"] for img in images if "url" in img]
        
        logger.debug(f"Found {len(image_urls)} images")
        return image_urls
