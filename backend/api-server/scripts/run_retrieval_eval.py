from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
import sys
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.core.database import SessionLocal
from app.services.retrieval_service import RetrievalService


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("cases_file_must_be_array")
    return [item for item in data if isinstance(item, dict)]


def compute_case_result(case: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    expected_document_names = {
        str(name).strip()
        for name in case.get("expected_document_names", [])
        if str(name).strip()
    }
    expected_hit_keywords = [
        str(keyword).strip().lower()
        for keyword in case.get("expected_hit_keywords", [])
        if str(keyword).strip()
    ]
    matched_rank = None
    strict_matched_rank = None
    for index, hit in enumerate(hits, start=1):
        document_name = str(hit.get("document_name") or "").strip()
        searchable_text = " ".join(
            [
                str(hit.get("document_name") or ""),
                str(hit.get("title") or ""),
                str(hit.get("snippet") or ""),
            ]
        ).lower()
        keyword_match = all(keyword in searchable_text for keyword in expected_hit_keywords)
        if document_name in expected_document_names and matched_rank is None:
            matched_rank = index
        if document_name in expected_document_names and keyword_match:
            strict_matched_rank = index
            break

    return {
        "id": str(case.get("id") or ""),
        "query": str(case.get("query") or ""),
        "tags": [str(tag) for tag in case.get("tags", [])],
        "expected_document_names": sorted(expected_document_names),
        "expected_hit_keywords": expected_hit_keywords,
        "matched_rank": matched_rank,
        "top1_hit": matched_rank == 1,
        "top3_hit": matched_rank is not None and matched_rank <= 3,
        "mrr": 0.0 if matched_rank is None else round(1.0 / matched_rank, 4),
        "strict_matched_rank": strict_matched_rank,
        "strict_top1_hit": strict_matched_rank == 1,
        "strict_top3_hit": strict_matched_rank is not None and strict_matched_rank <= 3,
        "strict_mrr": 0.0 if strict_matched_rank is None else round(1.0 / strict_matched_rank, 4),
        "top_hits": [
            {
                "rank": rank,
                "document_name": str(hit.get("document_name") or ""),
                "title": str(hit.get("title") or ""),
                "score": round(float(hit.get("score") or 0.0), 4),
            }
            for rank, hit in enumerate(hits[:3], start=1)
        ],
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    top1 = sum(1 for item in results if item["top1_hit"])
    top3 = sum(1 for item in results if item["top3_hit"])
    mrr = round(mean(item["mrr"] for item in results), 4) if results else 0.0
    strict_top1 = sum(1 for item in results if item["strict_top1_hit"])
    strict_top3 = sum(1 for item in results if item["strict_top3_hit"])
    strict_mrr = round(mean(item["strict_mrr"] for item in results), 4) if results else 0.0
    return {
        "count": total,
        "top1": top1,
        "top1_rate": 0.0 if total == 0 else round(top1 / total, 4),
        "top3": top3,
        "top3_rate": 0.0 if total == 0 else round(top3 / total, 4),
        "mrr": mrr,
        "strict_top1": strict_top1,
        "strict_top1_rate": 0.0 if total == 0 else round(strict_top1 / total, 4),
        "strict_top3": strict_top3,
        "strict_top3_rate": 0.0 if total == 0 else round(strict_top3 / total, 4),
        "strict_mrr": strict_mrr,
    }


def summarize_by_tag(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    tag_map: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        for tag in result["tags"]:
            tag_map.setdefault(tag, []).append(result)
    return {tag: summarize(items) for tag, items in sorted(tag_map.items())}


def print_report(
    *,
    project_id: int,
    kb_id: int,
    cases_path: Path,
    results: list[dict[str, Any]],
) -> None:
    overall = summarize(results)
    by_tag = summarize_by_tag(results)
    print(f"Retrieval Eval Report")
    print(f"project_id={project_id} kb_id={kb_id}")
    print(f"cases_file={cases_path}")
    print()
    print("Overall")
    print(json.dumps(overall, ensure_ascii=False, indent=2))
    print()
    print("By Tag")
    print(json.dumps(by_tag, ensure_ascii=False, indent=2))
    print()
    print("Per Case")
    for result in results:
        matched_rank = result["matched_rank"]
        strict_matched_rank = result["strict_matched_rank"]
        print(
            f"- {result['id']}: rank={matched_rank if matched_rank is not None else 'miss'} "
            f"top1={result['top1_hit']} top3={result['top3_hit']} "
            f"strict_rank={strict_matched_rank if strict_matched_rank is not None else 'miss'} "
            f"strict_top1={result['strict_top1_hit']} strict_top3={result['strict_top3_hit']} "
            f"tags={','.join(result['tags'])}"
        )
        print(f"  query={result['query']}")
        print(f"  expected={', '.join(result['expected_document_names'])}")
        if result["expected_hit_keywords"]:
            print(f"  strict_keywords={', '.join(result['expected_hit_keywords'])}")
        for hit in result["top_hits"]:
            print(
                f"  hit{hit['rank']}={hit['document_name']} | {hit['title']} | score={hit['score']}"
            )
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a retrieval-only evaluation against current NexusClaw retrieval service.")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--kb-id", type=int, required=True)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("retrieval_eval_cases_complex_docs.json"),
    )
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    db = SessionLocal()
    try:
        service = RetrievalService(db)
        results: list[dict[str, Any]] = []
        for case in cases:
            hits = service.retrieve(
                project_id=args.project_id,
                query=str(case.get("query") or ""),
                selected_kb_ids=[args.kb_id],
            )
            results.append(compute_case_result(case, hits))
    finally:
        db.close()

    payload = {
        "project_id": args.project_id,
        "kb_id": args.kb_id,
        "cases_file": str(args.cases),
        "overall": summarize(results),
        "by_tag": summarize_by_tag(results),
        "results": results,
    }
    if args.json_out is not None:
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(project_id=args.project_id, kb_id=args.kb_id, cases_path=args.cases, results=results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
