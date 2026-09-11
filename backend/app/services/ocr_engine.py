import io
from typing import List, Tuple, Dict, Any
import pymupdf
from PIL import Image
from backend.app.core.logging import logger

_ocr_engine = None

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
            logger.info("RapidOCR ONNX engine initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize RapidOCR engine: {e}")
            _ocr_engine = False
    return _ocr_engine

def run_ocr_on_image(img_bytes: bytes) -> str:
    """Runs RapidOCR on image bytes and returns 2D coordinate-reconstructed text lines."""
    engine = get_ocr_engine()
    if not engine:
        return ""
    try:
        results, elapse = engine(img_bytes)
        if not results:
            return ""
            
        boxes = []
        for r in results:
            if not r or len(r) < 2 or not r[1]:
                continue
            box, text = r[0], r[1]
            score = r[2] if len(r) > 2 else 0.95
            y_center = (box[0][1] + box[2][1]) / 2.0
            x_min = box[0][0]
            boxes.append({"y": y_center, "x": x_min, "text": text, "score": score})
            
        boxes.sort(key=lambda b: b["y"])
        rows = []
        for b in boxes:
            matched_row = None
            for row in rows:
                if abs(row["y"] - b["y"]) <= 14:
                    matched_row = row
                    break
            if matched_row:
                matched_row["items"].append(b)
                matched_row["y"] = sum(it["y"] for it in matched_row["items"]) / len(matched_row["items"])
            else:
                rows.append({"y": b["y"], "items": [b]})
                
        rows.sort(key=lambda r: r["y"])
        reconstructed_lines = []
        for r in rows:
            r["items"].sort(key=lambda it: it["x"])
            line_str = " | ".join(it["text"] for it in r["items"])
            reconstructed_lines.append(line_str)
            
        return "\n".join(reconstructed_lines)
    except Exception as e:
        logger.error(f"RapidOCR execution failed: {e}")
        return ""


def extract_pages_as_images_and_text(content: bytes, filename: str) -> Tuple[List[Image.Image], Dict[int, str]]:
    """
    Extracts high-resolution PIL images and text (Native or OCR) from the document.
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
                native_text = page.get_text("text") or ""
                
                # Render to high-DPI image for AI vision / OCR
                pix = page.get_pixmap(dpi=200)
                png_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                images.append(img)
                
                # If native text is missing or sparse, execute OCR on rendered page image
                if len(native_text.strip()) < 40:
                    logger.info(f"Page {page_num} of '{filename}' has sparse native text ({len(native_text.strip())} chars). Running OCR...")
                    ocr_text = run_ocr_on_image(png_bytes)
                    if ocr_text.strip():
                        text_by_page[page_num] = ocr_text
                        logger.info(f"Page {page_num} OCR successful: extracted {len(ocr_text.splitlines())} lines ({len(ocr_text)} chars).")
                    else:
                        text_by_page[page_num] = native_text
                else:
                    text_by_page[page_num] = native_text
                    logger.info(f"Page {page_num} using native PDF text ({len(native_text)} chars).")
                    
            pdf_doc.close()
        except Exception as e:
            logger.error(f"Error extracting pages from PDF {filename}: {str(e)}")
            raise
    else:
        # JPG / PNG
        try:
            img = Image.open(io.BytesIO(content)).convert("RGB")
            images.append(img)
            
            # Run OCR on image
            logger.info(f"Running OCR on image document '{filename}'...")
            ocr_text = run_ocr_on_image(content)
            text_by_page[1] = ocr_text
            logger.info(f"Image document OCR complete: extracted {len(ocr_text.splitlines())} lines.")
        except Exception as e:
            logger.error(f"Error opening image {filename}: {str(e)}")
            raise
            
    return images, text_by_page

def image_to_bytes(img: Image.Image, format: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()
