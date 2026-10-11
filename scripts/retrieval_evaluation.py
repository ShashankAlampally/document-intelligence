"""Deterministic passage judgments and metrics; no model-generated grading."""

import re
import unicodedata
from pathlib import Path

from app.search.evidence_text import cell_text, evidence_text


def normalize(text):
    text = unicodedata.normalize("NFKC", evidence_text(text)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def filename_key(name):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", name).casefold())


def evidence_groups(references):
    groups = {}
    for i, ref in enumerate(references):
        groups.setdefault(ref.get("evidence_id", str(i)), []).append(ref)
    return groups


def relevant(hit, reference, uploads):
    """Require bid, filename, physical PDF page and every content anchor."""
    return (
        hit["discovery_id"] == uploads[reference["bid"]]
        and filename_key(hit["file_name"]) == filename_key(reference["file"])
        and hit.get("page_number") == reference["page"]
        and all(
            f" {normalize(anchor)} "
            in " {} ".format(
                normalize(
                    cell_text(evidence_text(hit["text"]))
                    if hit.get("content_type") == "table"
                    else hit["text"]
                )
            )
            for anchor in reference["anchors"]
        )
    )


def score(hits, references, uploads, k=5):
    if not references:
        raise ValueError("Scored questions need at least one expected passage")
    ranks = []
    groups = evidence_groups(references)
    for alternatives in groups.values():
        ranks.append(
            next(
                (
                    i
                    for i, hit in enumerate(hits[:k], 1)
                    if any(relevant(hit, ref, uploads) for ref in alternatives)
                ),
                None,
            )
        )
    found = [rank for rank in ranks if rank is not None]
    return {
        "recall": len(found) / len(groups),
        "reciprocal_rank": 1 / min(found) if found else 0,
        "expected_passages": len(groups),
        "matched_passages": len(found),
        "first_relevant_rank": min(found) if found else None,
        "passage_ranks": ranks,
    }


def summarize(results, configurations):
    summary = []
    for name in configurations:
        rows = [row for row in results if row["configuration"] == name]
        successful = [row for row in rows if "metrics" in row]
        n = len(successful)
        summary.append(
            {
                "configuration": name,
                "evaluated_questions": n,
                "errors": len(rows) - n,
                "recall": sum(r["metrics"]["recall"] for r in successful) / n if n else None,
                "mrr": sum(r["metrics"]["reciprocal_rank"] for r in successful) / n if n else None,
            }
        )
    return summary


def write_review(dataset, path):
    lines = [
        "# Retrieval questions for review",
        "",
        f"Status: {dataset['status']}.",
        "",
        f"{len(dataset['questions'])} scored questions across both bids. "
        f"{len(dataset['abstention_checks'])} manual checks are excluded from retrieval metrics.",
        "",
        "PDF pages are physical, one-based pages in the supplied file, not printed page labels. "
        "HTML references have no invented page number. "
        "Questions are sent to search; references and notes are only used by the evaluator.",
        "",
    ]
    for q in dataset["questions"]:
        lines.extend(
            [
                f"## {q['id']} — {', '.join(q['bids'])}",
                "",
                q["question"],
                "",
                f"Reference: {q['reference_note']}",
                "",
            ]
        )
        for ref in q["expected_passages"] + q.get("supporting_passages", []):
            loc = f"PDF page {ref['page']}" if ref["page"] else "HTML"
            role = (
                ref.get("evidence_id", "required evidence")
                if ref in q["expected_passages"]
                else "supporting context; not scored"
            )
            lines.append(f"- **{ref['bid']} / {ref['file']} — {loc}** ({role})")
            lines.extend(f"  - Evidence anchor: `{anchor}`" for anchor in ref["anchors"])
        lines.append("")
    for q in dataset["abstention_checks"]:
        lines.extend(
            [
                f"## {q['id']} — manual abstention check",
                "",
                q["question"],
                "",
                q["reference_note"],
                "",
            ]
        )
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_report(record, path):
    k = record["k"]
    lines = [
        "# Retrieval evaluation report",
        "",
        f"Status: **{record['status']}**. References: {record.get('dataset_status', 'draft')}.",
        "",
        f"Dataset SHA-256: `{record['dataset_sha256']}`",
        "",
        "| Configuration | Questions | Errors | Recall@" + str(k) + " | MRR@" + str(k) + " |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in record["summary"]:

        def number(value):
            return f"{value:.4f}" if value is not None else "Unavailable"

        lines.append(
            f"| {row['configuration']} | {row['evaluated_questions']} | {row['errors']} "
            f"| {number(row['recall'])} | {number(row['mrr'])} |"
        )
    lines.extend(
        [
            "",
            "## Method",
            "",
            "Recall is the fraction of annotated evidence units recovered, averaged per question. "
            "MRR uses the first result matching any expected unit. Overlapping chunks cannot "
            "increase a unit's recall above one. Alternatives sharing an evidence_id satisfy the "
            "same unit; supporting context is not required for credit. Filename matching ignores "
            "case and punctuation, while bid, physical page and content must match. "
            "Table JSON cells and explicitly typed table fragments are decoded before matching. "
            "A correct file/page without the required "
            "content anchors earns no credit.",
            "",
            "These are annotated evidence-unit metrics, not exhaustive relevance judgments over "
            "every corpus chunk. Exact normalized anchors make grading reproducible but may "
            "under-credit differently extracted or split text. Inspect saved misses before "
            "drawing conclusions; do not tune references to favor retrieved results.",
            "",
            "All configurations use the same immutable question set, selected uploads and top-k. "
            "Cross-bid search gets k candidates per bid, merges by the configuration's score, "
            "then keeps k total. References never enter search. "
            "No LLM generation or grader is used. "
            "Latency includes local inference/cache effects and is diagnostic, "
            "not a controlled benchmark.",
            "",
            "Errors are recorded separately and make the run incomplete; their questions are not "
            "silently scored as retrieval misses. Only complete runs should be compared.",
            "",
            "## Questions with missing expected evidence",
            "",
        ]
    )
    for row in record["results"]:
        if "error" in row or row["metrics"]["recall"] < 1:
            detail = row.get("error") or f"passage ranks: {row['metrics']['passage_ranks']}"
            lines.append(f"- {row['configuration']} / {row['id']}: {detail}")
    lines.extend(["", "## Evidence units unavailable as a single indexed chunk", ""])
    absent = record.get("reference_units_absent_from_index", [])
    if not absent:
        lines.append("Every annotated evidence unit has at least one matching indexed chunk.")
    for unit in absent:
        lines.append(
            f"- {unit['id']} / unit {unit['unit']}: "
            f"{unit['bid']} / {unit['file']} / page {unit['page']}. "
            "The complete anchor set does not coexist in a stored chunk. "
            "This limits achievable recall under the strict matching rule; "
            "review annotation granularity and chunk boundaries before diagnosing ranking."
        )
    lines.extend(
        [
            "",
            "Full configuration, source/index fingerprints, metrics and exact returned "
            "passages are in the adjacent results JSON. All manual missing-field checks "
            "are excluded from these metrics.",
            "",
        ]
    )
    Path(path).write_text("\n".join(lines), encoding="utf-8")
