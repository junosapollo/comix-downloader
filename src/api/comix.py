"""
Comix.to API wrapper for manga information and chapter data.
"""

import json
import re
from typing import Optional
from playwright.sync_api import sync_playwright
from ..utils.retry import retry_with_backoff
from ..utils.logger import get_logger
from ..utils.session import get_session
from ..utils.hash import generate_comix_hash

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
    def get_manga_info(cls, manga_code: str) -> Optional[any]:
        """Fetch manga information from DOM using Playwright."""
        from ..core.models import MangaInfo
        url = f"https://comix.to/title/{manga_code}"
        logger.info(f"Fetching manga info using Playwright for {manga_code}...")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                # Navigate to the page
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # Wait for the initial-data script tag to be present in the DOM
                page.wait_for_selector('script#initial-data', state="attached", timeout=10000)
                
                # Get initial data contents
                initial_data_str = page.locator('script#initial-data').inner_html()
                json_data = json.loads(initial_data_str)
                
                browser.close()
        except Exception as e:
            logger.error(f"Playwright failed to fetch manga info for {manga_code}: {e}")
            return None

        # Find the manga detail query in the json_data
        manga_detail = None
        queries = json_data.get("queries", {})
        for key, val in queries.items():
            if "manga" in key and "detail" in key and manga_code in key:
                manga_detail = val
                break
                
        if not manga_detail:
            logger.error(f"Could not find manga detail in initial-data for {manga_code}. Keys: {list(queries.keys())}")
            return None
            
        # Get alt titles safely
        alt_titles = manga_detail.get("altTitles", [])
        if not isinstance(alt_titles, list):
            alt_titles = [alt_titles] if alt_titles else []
            
        # Poster URL
        poster = manga_detail.get("poster") or {}
        poster_url = None
        if isinstance(poster, dict):
            poster_url = poster.get("large") or poster.get("medium")
            
        genres = []
        for g in manga_detail.get("genres", []):
            if isinstance(g, dict) and "title" in g:
                genres.append(g["title"])
            elif isinstance(g, str):
                genres.append(g)

        return MangaInfo(
            manga_id=manga_detail.get("id"),
            hash_id=manga_detail.get("hid"),
            title=manga_detail.get("title", "Unknown"),
            alt_titles=alt_titles,
            slug=manga_detail.get("url", "").split("/")[-1] if manga_detail.get("url") else None,
            rank=manga_detail.get("rank"),
            manga_type=manga_detail.get("type"),
            poster_url=poster_url,
            original_language=manga_detail.get("originalLanguage"),
            status=manga_detail.get("status"),
            final_chapter=str(manga_detail.get("finalChapter") or 0),
            latest_chapter=str(manga_detail.get("latestChapter") or 0),
            start_date=manga_detail.get("startDate"),
            end_date=manga_detail.get("endDate"),
            rated_avg=manga_detail.get("ratedAvg"),
            rated_count=manga_detail.get("ratedCount"),
            follows_total=manga_detail.get("followsTotal"),
            is_nsfw=manga_detail.get("contentRating") == "nsfw",
            year=manga_detail.get("year"),
            genres=genres,
            description=manga_detail.get("synopsis", "")
        )
    
    @classmethod
    def get_all_chapters(cls, manga_code: str) -> list[any]:
        """Fetch all chapters for a manga using Playwright DOM scraping."""
        from ..core.models import Chapter
        url = f"https://comix.to/title/{manga_code}"
        logger.info(f"Scraping chapters using Playwright for {manga_code}...")
        
        scrape_js = """() => {
            return Array.from(document.querySelectorAll('.mchap-item')).map(li => {
                const a = li.querySelector('.mchap-row__primary');
                const ch = li.querySelector('.mchap-row__ch');
                const ti = li.querySelector('.mchap-row__title');
                const gp = li.querySelector('.mchap-row__group');
                return {
                    href: a ? a.getAttribute('href') : null,
                    chap_label: ch ? ch.textContent.trim() : null,
                    title: ti ? ti.textContent.trim() : null,
                    group: gp ? (gp.querySelector('span') ? gp.querySelector('span').textContent.trim() : gp.textContent.trim()) : null,
                    group_official: gp ? gp.classList.contains('is-official') : false,
                };
            });
        }"""
        
        chapters: list[Chapter] = []
        seen_ids = set()
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                prev_first_href = None
                consecutive_dup_pages = 0
                max_pages = 200
                
                for page_n in range(1, max_pages + 1):
                    page_url = f"{url}?page={page_n}"
                    page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
                    
                    if prev_first_href is None:
                        try:
                            page.wait_for_selector(".mchap-row__primary", timeout=10000)
                        except Exception:
                            # If page 1 doesn't render any chapter links, there are none
                            logger.warning(f"No chapters found on page 1 for {manga_code}")
                            break
                    else:
                        # Wait for React to swap the page content
                        import json as std_json
                        js_predicate = (
                            "(() => { const a = document.querySelector('.mchap-row__primary'); "
                            f"return a && a.getAttribute('href') !== {std_json.dumps(prev_first_href)}; }})"
                        )
                        try:
                            page.wait_for_function(js_predicate, timeout=5000)
                        except Exception:
                            # If it didn't change, we likely hit the end or it failed to render new content
                            pass
                            
                    rows = page.evaluate(scrape_js) or []
                    if not rows:
                        break
                        
                    prev_first_href = rows[0].get("href")
                    page_added = 0
                    
                    for row in rows:
                        href = row.get("href")
                        if not href:
                            continue
                        
                        # Parse `/title/{slug}/{chap_id}-chapter-{chap_num}`
                        m = re.match(r".*/title/[^/]+/(\d+)-chapter-(.+)$", href)
                        if not m:
                            continue
                        
                        chap_id_str, chap_num_str = m.group(1), m.group(2)
                        if chap_id_str in seen_ids:
                            continue
                            
                        seen_ids.add(chap_id_str)
                        
                        group = row.get("group")
                        if not group and row.get("group_official"):
                            group = "Official"
                            
                        chapters.append(Chapter(
                            chapter_id=int(chap_id_str),
                            number=chap_num_str,
                            title=row.get("title") or f"Chapter {chap_num_str}",
                            volume=None,
                            votes=0,
                            group_name=group,
                            pages_count=0
                        ))
                        page_added += 1
                        
                    if page_added == 0:
                        consecutive_dup_pages += 1
                        if consecutive_dup_pages >= 2:
                            break
                    else:
                        consecutive_dup_pages = 0
                        
                browser.close()
        except Exception as e:
            logger.error(f"Playwright failed to fetch chapters for {manga_code}: {e}")
            
        # Reverse the list so old chapters (low numbers) are at the beginning
        chapters.reverse()
        logger.info(f"Found {len(chapters)} chapters using Playwright DOM scraping")
        return chapters
    
    @classmethod
    @retry_with_backoff()
    def get_chapter_images(cls, chapter_id: int) -> list[str]:
        """Fetch all image URLs for a chapter."""
        base_path = f"/chapters/{chapter_id}/"
        time_val = 1
        
        request_hash = generate_comix_hash(base_path, time=time_val)
        url = f"{cls.BASE_URL}{base_path}?time={time_val}&_={request_hash}"
        
        logger.debug(f"Fetching images for chapter {chapter_id} (hash used)")
        
        response = get_session().get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        images = (data.get("result") or {}).get("images", [])
        image_urls = [img["url"] for img in images if "url" in img]
        
        logger.debug(f"Found {len(image_urls)} images")
        return image_urls
