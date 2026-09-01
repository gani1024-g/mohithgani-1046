"""
DocuSense AI document ingestion pipeline.
PostgreSQL + pgvector compatible.
"""

import io
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import fitz
import filetype
import pytesseract
from PIL import Image
import numpy as np
from huggingface_hub import InferenceClient

TESSERACT_MODEL_NAME = "eng"

if os.name == "nt":
    TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    if not os.path.isfile(TESSERACT_CMD):
        raise RuntimeError(
            f"Tesseract executable not found at: {TESSERACT_CMD}"
        )

    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
else:
    TESSERACT_CMD = "tesseract"

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "image/png": "png",
    "image/jpeg": "jpg",
}

HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN environment variable is not set.")

embedding_client = InferenceClient(
    model="BAAI/bge-small-en-v1.5",
    token=HF_TOKEN,
    timeout=60,
)


def validate_file_magic(file_bytes: bytes, max_size_mb: int = 50) -> str:
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    if len(file_bytes) > max_size_mb * 1024 * 1024:
        raise ValueError(f"File size exceeds maximum limit of {max_size_mb} MB")

    kind = filetype.guess(file_bytes)
    mime = kind.mime if kind else "application/octet-stream"

    if mime not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported file format: {mime}")

    return mime

def extract_page_text_and_boxes(page: fitz.Page) -> Tuple[str, List[Dict]]:
    rect = page.rect
    total_area = rect.width * rect.height
    text_blocks = page.get_text("blocks")

    extracted_text = ""
    block_records: List[Dict[str, Any]] = []
    text_char_count = 0

    for block in text_blocks:
        if len(block) >= 7 and block[6] == 0:
            block_text = block[4].strip()
            if block_text:
                extracted_text += block_text + "\n"
                text_char_count += len(block_text)
                block_records.append(
                    {
                        "text": block_text,
                        "bbox": {
                            "x0": block[0],
                            "y0": block[1],
                            "x1": block[2],
                            "y1": block[3],
                        },
                    }
                )

    char_density = (text_char_count * 50) / max(total_area, 1.0)

    if char_density < 0.20 or not extracted_text.strip():
        pix = page.get_pixmap(dpi=200)
        image = Image.open(io.BytesIO(pix.tobytes("png")))
        ocr_data = pytesseract.image_to_data(
            image,
            lang=TESSERACT_MODEL_NAME,
            output_type=pytesseract.Output.DICT,
        )

        extracted_text = ""
        block_records = []
        n_boxes = len(ocr_data["text"])

        scale_x = rect.width / max(pix.width, 1)
        scale_y = rect.height / max(pix.height, 1)

        for i in range(n_boxes):
            word = ocr_data["text"][i].strip()
            if word:
                extracted_text += word + " "
                x = ocr_data["left"][i]
                y = ocr_data["top"][i]
                w = ocr_data["width"][i]
                h = ocr_data["height"][i]
                block_records.append(
                    {
                        "text": word,
                        "bbox": {
                            "x0": x * scale_x,
                            "y0": y * scale_y,
                            "x1": (x + w) * scale_x,
                            "y1": (y + h) * scale_y,
                        },
                    }
                )

    return extracted_text.strip(), block_records


def build_semantic_chunks(
    doc_id: int,
    page_num: int,
    blocks: List[Dict],
    target_tokens: int = 768,
    overlap_pct: float = 0.10,
) -> List[Dict]:
    chunks: List[Dict] = []
    current_tokens: List[str] = []
    current_bboxes: List[Dict] = []
    overlap_tokens_count = max(1, int(target_tokens * overlap_pct))
    chunk_index = 0

    for block in blocks:
        words = block["text"].split()
        for word in words:
            current_tokens.append(word)
            current_bboxes.append(block["bbox"])

            if len(current_tokens) >= target_tokens:
                content = " ".join(current_tokens)
                agg_bbox = {
                    "x0": min(b["x0"] for b in current_bboxes),
                    "y0": min(b["y0"] for b in current_bboxes),
                    "x1": max(b["x1"] for b in current_bboxes),
                    "y1": max(b["y1"] for b in current_bboxes),
                }
                chunks.append(
                    {
                        "doc_id": doc_id,
                        "chunk_index": chunk_index,
                        "page_num": page_num,
                        "content": content,
                        "bbox_json": json.dumps(agg_bbox),
                        "token_count": len(current_tokens),
                    }
                )
                chunk_index += 1
                current_tokens = current_tokens[-overlap_tokens_count:]
                current_bboxes = current_bboxes[-overlap_tokens_count:]

    if current_tokens:
        content = " ".join(current_tokens)
        agg_bbox = {
            "x0": min(b["x0"] for b in current_bboxes),
            "y0": min(b["y0"] for b in current_bboxes),
            "x1": max(b["x1"] for b in current_bboxes),
            "y1": max(b["y1"] for b in current_bboxes),
        }
        chunks.append(
            {
                "doc_id": doc_id,
                "chunk_index": chunk_index,
                "page_num": page_num,
                "content": content,
                "bbox_json": json.dumps(agg_bbox),
                "token_count": len(current_tokens),
            }
        )

    return chunks


def process_document_pipeline(
    doc_id: int,
    file_bytes: bytes,
) -> Tuple[int, List[Dict]]:
    mime = validate_file_magic(file_bytes)
    if mime != "application/pdf":
        raise ValueError("The semantic PDF pipeline only accepts PDF files.")

    pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        page_count = len(pdf_doc)
        all_chunks: List[Dict] = []

        for page_idx in range(page_count):
            page = pdf_doc.load_page(page_idx)
            _, blocks = extract_page_text_and_boxes(page)
            all_chunks.extend(build_semantic_chunks(doc_id, page_idx + 1, blocks))

        if all_chunks:
            for chunk in all_chunks:
                text = chunk["content"].strip()

                if not text:
                    continue

                embedding = embedding_client.feature_extraction(
                    text,
                    normalize=True,
                )

                vector = np.asarray(
                    embedding,
                    dtype=np.float32,
                ).reshape(-1)

                if vector.shape[0] != 384:
                    raise ValueError(
                        f"Expected 384-dimensional embedding, got {vector.shape[0]}"
                    )

                chunk["embedding"] = vector.tolist()

        return page_count, all_chunks
    finally:
        pdf_doc.close()
