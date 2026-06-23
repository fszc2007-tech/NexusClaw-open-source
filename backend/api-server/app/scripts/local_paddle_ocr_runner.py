from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local PaddleOCR and emit normalized JSON.")
    parser.add_argument("--file", required=True, help="Absolute path to input image or pdf.")
    parser.add_argument("--det-model-dir", required=False, help="Detection model directory.")
    parser.add_argument("--rec-model-dir", required=False, help="Recognition model directory.")
    parser.add_argument("--lang", default="ch", help="OCR language.")
    parser.add_argument("--ocr-version", default="PP-OCRv5", help="OCR version.")
    return parser.parse_args()


def normalize_poly(poly: Any) -> list[list[int]] | None:
    if poly is None:
        return None
    if hasattr(poly, "tolist"):
        poly = poly.tolist()
    normalized: list[list[int]] = []
    for point in poly:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            normalized.append([int(point[0]), int(point[1])])
    return normalized or None


def build_payload(result_items: list[Any]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    full_text_parts: list[str] = []
    for page_idx, item in enumerate(result_items, start=1):
        page_no = (item.get("page_index") if isinstance(item, dict) else None) or page_idx
        rec_texts = list(item.get("rec_texts") or []) if isinstance(item, dict) else []
        rec_scores = list(item.get("rec_scores") or []) if isinstance(item, dict) else []
        rec_polys = list(item.get("rec_polys") or item.get("dt_polys") or []) if isinstance(item, dict) else []
        page_lines: list[str] = []
        for index, text in enumerate(rec_texts, start=1):
            normalized = str(text).strip()
            if not normalized:
                continue
            page_lines.append(normalized)
            blocks.append(
                {
                    "block_type": "paragraph",
                    "text": normalized,
                    "page_no": int(page_no),
                    "order_no": len(blocks) + 1,
                    "metadata": {
                        "score": float(rec_scores[index - 1]) if index - 1 < len(rec_scores) and rec_scores[index - 1] is not None else None,
                        "bbox": normalize_poly(rec_polys[index - 1]) if index - 1 < len(rec_polys) else None,
                    },
                }
            )
        if page_lines:
            full_text_parts.append("\n".join(page_lines))

    text = "\n\n".join(full_text_parts).strip()
    return {
        "parser_name": "local_paddle_ocr",
        "provider": "PaddleOCR",
        "page_count": len(result_items),
        "block_count": len(blocks),
        "text": text,
        "blocks": blocks,
    }


def main() -> int:
    args = parse_args()
    target_file = Path(args.file).expanduser().resolve()
    if not target_file.exists():
        print(json.dumps({"error": f"file_not_found: {target_file}"}))
        return 2

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("PADDLE_LOG_LEVEL", "ERROR")
    os.environ.setdefault("GLOG_minloglevel", "3")

    with contextlib.redirect_stdout(sys.stderr):
        from paddleocr import PaddleOCR

        kwargs: dict[str, Any] = {
            "lang": args.lang,
            "ocr_version": args.ocr_version,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        }
        if args.det_model_dir:
            kwargs["text_detection_model_dir"] = args.det_model_dir
        if args.rec_model_dir:
            kwargs["text_recognition_model_dir"] = args.rec_model_dir
        ocr = PaddleOCR(**kwargs)
        result_items = list(ocr.predict(str(target_file)))

    payload = build_payload(result_items)
    if not payload["text"]:
        print(json.dumps({"error": "ocr_empty_result"}))
        return 3
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
