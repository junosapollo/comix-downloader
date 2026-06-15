"""
Session management (FlareSolverr removed).
"""

import requests
import time
import threading
from typing import Any
from .logger import get_logger

logger = get_logger(__name__)

class SessionManager:
    """Manages requests session (FlareSolverr removed)."""
    
    def __init__(self):
        self.session = requests.Session()
        self._lock = threading.Lock()
        # Set default headers
        self.session.headers.update({
            "Referer": "https://comix.to/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        })

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """Execute a GET request directly."""
        # Pop force_flare if present
        kwargs.pop("force_flare", None)
        
        try:
            response = self.session.get(url, **kwargs)
            
            # Handle rate limiting if status code is 429
            if response.status_code == 429:
                logger.warning(f"Rate limited (429) for {url}. Waiting 5 seconds...")
                time.sleep(5)
                response = self.session.get(url, **kwargs)
                
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

# Singleton instance
_session_manager = None

def get_session() -> SessionManager:
    """Get the singleton session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
