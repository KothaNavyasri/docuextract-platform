import io
from typing import List, Tuple, Dict
import pymupdf
from PIL import Image
from backend.app.core.logging import logger

def extract_pages_as_images_and_text(content: bytes, filename: str) -> Tuple[List[Image.Image], Dict[int, str]]:
    """
    Extracts high-resolution PIL images and any native text from the document.
    Returns:
        (list_of_pil_images, {page_num_1_indexed: text})
    """
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    images: List[Image.Image] = []
    text_by_page: Dict[int, str] = {}
    
    if ext == ".pdf":
        try:
            pdf_doc = pymupdf.open(stream=content, filetype="pdf")
            for i, page in enumerate(pdf_doc):
                page_num = i + 1
                page_text = page.get_text("text") or ""
                text_by_page[page_num] = page_text
                
                # Render to high-DPI image for AI vision / OCR
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                images.append(img)
            pdf_doc.close()
        except Exception as e:
            logger.error(f"Error extracting pages from PDF {filename}: {str(e)}")
            raise
    else:
        # JPG / PNG
        try:
            img = Image.open(io.BytesIO(content)).convert("RGB")
            images.append(img)
            text_by_page[1] = ""
        except Exception as e:
            logger.error(f"Error opening image {filename}: {str(e)}")
            raise
            
    return images, text_by_page

def image_to_bytes(img: Image.Image, format: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()
