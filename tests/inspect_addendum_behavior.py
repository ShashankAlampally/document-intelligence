"""Live prompt check with fictional evidence; no indexing or search is performed."""

import argparse
import json
from uuid import uuid4

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.nodes.extract_fields import extract_fields
from app.agents.qa.graph.state import WorkflowState
from app.agents.qa.nodes.generate_answer import generate_answer
from app.config import Settings
from app.shared.groq_client import GroqModel

CASES = {
    "amendment": (
        "Addendum 1.pdf",
        "addendum",
        "Addendum 1 changes the submission deadline from June 10, 2024 to June 15, 2024.",
    ),
    "conflict": (
        "bid-page.html",
        "bid_page",
        "Submission deadline: June 12, 2024. No issue date stated.",
    ),
    "unrelated": (
        "Addendum 1.pdf",
        "addendum",
        "Addendum 1 changes required RAM from 16 GB to 32 GB.",
    ),
}


def evidence_for(case: str) -> list[dict]:
    name, doc_type, text = CASES[case]
    original = {
        "chunk_id": "original",
        "file_name": "original-rfp.pdf",
        "page_number": 2,
        "section": None,
        "doc_type": "rfp",
        "addendum_number": None,
        "text": "Submission deadline: June 10, 2024.",
    }
    other = {
        **original,
        "chunk_id": "other",
        "file_name": name,
        "doc_type": doc_type,
        "text": text,
        "page_number": 1,
    }
    if doc_type == "addendum":
        other["addendum_number"] = 1
    else:
        other["page_number"] = None
        other["section"] = "section-2"
    return [original, other]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=list(CASES), required=True)
    args = parser.parse_args()
    settings = Settings()
    model = GroqModel(settings)
    evidence = evidence_for(args.case)
    print("FICTIONAL evidence: this checks final model interpretation, not retrieval.", flush=True)
    qa = generate_answer(
        WorkflowState(
            evidence=evidence,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "What is the submission deadline? Explain differing values, if present.\n"
                        "Retrieved evidence:\n" + json.dumps(evidence)
                    ),
                }
            ],
        ),
        model,
    )
    extraction = extract_fields(
        ExtractionState(
            evidence=evidence,
            requested_fields=["Due Date"],
        ),
        model,
    )
    record = {"case": args.case, "fictional": True, "evidence": evidence}
    for name, result in [("qa", qa), ("extraction", extraction)]:
        draft = result.get("draft")
        output = None
        if draft is not None:
            output = draft.model_dump()
        record[name] = {"output": output, "error": result.get("error"), "trace": result["trace"]}
        print(name, json.dumps(record[name]["output"], indent=2))
        if result.get("error"):
            print(result["error"])
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    path = settings.log_dir / f"addendum-check-{uuid4()}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Trace: {path}")
    if qa.get("error") or extraction.get("error"):
        parser.exit(1, "Live prompt check failed; inspect the trace.\n")


if __name__ == "__main__":
    main()
