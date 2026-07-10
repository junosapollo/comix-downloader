"""
PDF creation from downloaded images.
"""

from pathlib import Path
from io import BytesIO
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _part_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.name}.part")


def _load_image_for_pdf(source) -> Image.Image:
    img = Image.open(source)
    img.load()

    if img.mode in ('RGBA', 'LA', 'P'):
        if img.mode == 'P':
            img = img.convert('RGBA')
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        return background

    if img.mode != 'RGB':
        return img.convert('RGB')

    return img


def _write_pdf(images: list[tuple[int, Image.Image]], output_path: Path, title: str) -> Path:
    if not images:
        raise ValueError("No valid images provided for PDF creation")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _part_path(output_path)
    if tmp_path.exists():
        tmp_path.unlink()

    try:
        c = canvas.Canvas(str(tmp_path))
        c.setTitle(title)

        for idx, img in images:
            img_width, img_height = img.size
            c.setPageSize((img_width, img_height))

            img_buffer = BytesIO()
            img.save(img_buffer, format='JPEG', quality=95)
            img_buffer.seek(0)

            c.drawImage(ImageReader(img_buffer), 0, 0, img_width, img_height)
            c.showPage()
            logger.debug(f"Added page {idx} to PDF")

        c.save()
        tmp_path.replace(output_path)
        logger.info(f"Created PDF: {output_path}")
        return output_path
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def create_pdf(
    image_paths: list[Path],
    output_path: str | Path,
    title: str = "Manga Chapter"
) -> Path:
    """
    Create a PDF from a list of image files.
    
    Args:
        image_paths: List of image file paths
        output_path: Output PDF file path
        title: PDF title metadata
    
    Returns:
        Path to created PDF
    """
    output_path = Path(output_path)
    images = [
        (idx, _load_image_for_pdf(img_path))
        for idx, img_path in enumerate(sorted(image_paths), 1)
    ]
    return _write_pdf(images, output_path, title)


def create_pdf_from_bytes(
    image_data: list[tuple[int, bytes]],
    output_path: str | Path,
    title: str = "Manga Chapter"
) -> Path:
    """
    Create a PDF directly from image bytes without saving to disk first.
    
    Args:
        image_data: List of (index, image_bytes) tuples
        output_path: Output PDF file path
        title: PDF title metadata
    
    Returns:
        Path to created PDF
    """
    output_path = Path(output_path)
    images = [
        (idx, _load_image_for_pdf(BytesIO(data)))
        for idx, data in sorted(image_data, key=lambda x: x[0])
    ]
    return _write_pdf(images, output_path, title)
