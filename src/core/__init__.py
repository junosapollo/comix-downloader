from .models import MangaInfo, Chapter, DownloadConfig

__all__ = ["MangaInfo", "Chapter", "DownloadConfig", "MangaDownloader"]


def __getattr__(name):
    if name == "MangaDownloader":
        from .downloader import MangaDownloader

        return MangaDownloader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
