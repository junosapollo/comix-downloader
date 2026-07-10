"""
Image saving utilities.
"""

from pathlib import Path
from io import BytesIO
from PIL import Image
from ..utils.logger import get_logger

logger = get_logger(__name__)


def validate_image_bytes(data: bytes) -> None:
    """Raise ValueError if bytes are not a readable image."""
    try:
        with Image.open(BytesIO(data)) as img:
            img.verify()
    except Exception as e:
        raise ValueError(f"Invalid image data: {e}") from e


def get_image_extension(data: bytes) -> str:
    """Determine image extension from validated image bytes."""
    validate_image_bytes(data)

    with Image.open(BytesIO(data)) as img:
        image_format = (img.format or "").upper()

    if image_format == "PNG":
        return ".png"
    if image_format in ("JPEG", "JPG"):
        return ".jpg"
    if image_format == "GIF":
        return ".gif"
    if image_format == "WEBP":
        return ".webp"
    return ".jpg"


def save_images(
    image_data: list[tuple[int, bytes]],
    output_dir: str | Path,
    chapter_name: str
) -> list[Path]:
    """
    Save downloaded images to a folder.
    
    Args:
        image_data: List of (index, image_bytes) tuples
        output_dir: Base output directory
        chapter_name: Chapter folder name
    
    Returns:
        List of saved image paths
    """
    chapter_dir = Path(output_dir) / chapter_name
    chapter_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    
    for idx, data in sorted(image_data, key=lambda x: x[0]):
        # Determine file extension from data
        ext = get_image_extension(data)
        filename = f"{idx:03d}{ext}"
        filepath = chapter_dir / filename
        
        with open(filepath, "wb") as f:
            f.write(data)
        
        saved_paths.append(filepath)
        logger.debug(f"Saved image: {filepath}")
    
    logger.info(f"Saved {len(saved_paths)} images to {chapter_dir}")
    return saved_paths


def _get_image_extension(data: bytes) -> str:
    """Determine image extension from file header."""
    return get_image_extension(data)


def cleanup_images(image_paths: list[Path]) -> None:
    """Delete image files after conversion."""
    for path in image_paths:
        try:
            path.unlink()
            logger.debug(f"Deleted: {path}")
        except OSError as e:
            logger.warning(f"Failed to delete {path}: {e}")
    
    # Try to remove empty directory
    if image_paths:
        parent = image_paths[0].parent
        try:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                logger.debug(f"Removed empty directory: {parent}")
        except OSError:
            pass
