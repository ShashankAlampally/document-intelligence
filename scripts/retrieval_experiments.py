"""Compare candidate counts and optional grouping using one fixed question set."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from statistics import median
from uuid import UUID


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bid1", type=UUID, required=True)
    parser.add_argument("--bid2", type=UUID, required=True)
    parser.add_argument("--grouped-bid1", type=UUID)
    parser.add_argument("--grouped-bid2", type=UUID)
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/retrieval/experiments"))
    parser.add_argument(
        "--profiles", nargs="+", choices=["existing", "grouped"], default=["existing", "grouped"]
    )
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    if args.summarize_only:
        args.profiles = []
    if "grouped" in args.profiles and not (args.grouped_bid1 and args.grouped_bid2):
        parser.error("Grouped runs require both grouped discovery IDs")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    comparisons = []
    for profile, bid1, bid2 in [
        ("existing", args.bid1, args.bid2),
        ("grouped", args.grouped_bid1, args.grouped_bid2),
    ]:
        if profile not in args.profiles:
            continue
        for candidates in [20, 40, 60]:
            name = f"{profile}-{candidates}"
            output = args.output_dir / f"{name}.json"
            configs = (
                ["vector", "hybrid", "hybrid_rerank"] if candidates == 20 else ["hybrid_rerank"]
            )
            command = [
                sys.executable,
                "-m",
                "scripts.evaluate_retrieval",
                "--bid1",
                str(bid1),
                "--bid2",
                str(bid2),
                "--candidates",
                str(candidates),
                "--configurations",
                *configs,
                "--output",
                str(output),
            ]
            print(f"Running {name}: {', '.join(configs)}", flush=True)
            with (args.output_dir / f"{name}.log").open("w") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
            record = json.loads(output.read_text())
            if record["status"] != "completed":
                raise RuntimeError(f"Incomplete run: {output}")
            print(f"Completed {name}", flush=True)
    for profile in ["existing", "grouped"]:
        for candidates in [20, 40, 60]:
            output = args.output_dir / f"{profile}-{candidates}.json"
            if not output.exists():
                continue
            record = json.loads(output.read_text())
            if record["status"] != "completed":
                raise RuntimeError(f"Incomplete run: {output}")
            expected = args.bid1 if profile == "existing" else args.grouped_bid1
            if expected and record["uploads"]["Bid1"] != str(expected):
                raise RuntimeError(f"Run belongs to a different Bid1 index: {output}")
            expected = args.bid2 if profile == "existing" else args.grouped_bid2
            if expected and record["uploads"]["Bid2"] != str(expected):
                raise RuntimeError(f"Run belongs to a different Bid2 index: {output}")
            if record["k"] != 5 or any(
                opts["rerank_candidates"] != candidates
                for opts in record["configurations"].values()
            ):
                raise RuntimeError(f"Unexpected cutoff or candidate settings: {output}")
            for row in record["summary"]:
                timings = [
                    r["elapsed_seconds"]
                    for r in record["results"]
                    if r["configuration"] == row["configuration"]
                ]
                comparisons.append(
                    dict(
                        profile=profile,
                        candidates=candidates,
                        median_seconds=median(timings),
                        output=str(output),
                        **row,
                    )
                )
    records = [json.loads(Path(row["output"]).read_text()) for row in comparisons]
    if len({r["dataset_sha256"] for r in records}) != 1:
        raise RuntimeError("Experiments used different question sets")
    result = dict(
        status="completed" if len(comparisons) == 10 else "partial",
        dataset_sha256=records[0]["dataset_sha256"],
        k=5,
        comparisons=comparisons,
    )
    (args.output_dir / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = [
        "# Retrieval experiments",
        "",
        "All experiments use the same 19 scored questions, decoded-table scoring and k=5. "
        "The manual bond check is excluded. No LLM calls are made.",
        "",
        "| Index | Candidates | Search | Recall@5 | MRR@5 | Median seconds/question |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for row in comparisons:
        lines.append(
            f"| {row['profile']} | {row['candidates']} | {row['configuration']} "
            f"| {row['recall']:.4f} | {row['mrr']:.4f} | {row['median_seconds']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The candidate setting applies to hybrid/reranking pools; direct vector-only "
            "search retrieves five results without a reranking pool. "
            "Compare candidate counts within one index to isolate reranking-depth changes. "
            "Compare existing versus grouped at the same count to assess grouping. "
            "Grouping uses the same 1000-character limit and 100-character overlap, "
            "regroups the fixed saved corpus at numbered addendum question/answer boundaries, "
            "and renders table cells "
            "with headers as readable text while retaining existing row metadata. "
            "Unchanged vectors are reused. "
            "Current parser changes are excluded from this controlled comparison.",
            "",
            "Timing is diagnostic and includes local cache/runtime effects; this is not "
            "a controlled latency benchmark. Scores on this small development set do not "
            "prove improved Q&A/extraction accuracy or unseen-bid generalization.",
            "",
            "original-scoring/ preserves the previous results. Compare them only with "
            "existing-20 to identify scoring corrections; that is not retrieval improvement.",
            "",
        ]
    )
    if len(comparisons) == 10:
        best = max(comparisons, key=lambda row: (row["recall"], row["mrr"]))
        original_rerank = [
            row
            for row in comparisons
            if row["profile"] == "existing" and row["configuration"] == "hybrid_rerank"
        ]
        depth = min(
            original_rerank, key=lambda row: (-row["recall"], -row["mrr"], row["candidates"])
        )
        recommendation = dict(
            keep_scoring_correction=True,
            enable_grouping=best["profile"] == "grouped",
            rerank_candidates=depth["candidates"],
            best_recall=best,
            limitation="Development-set retrieval only; no Q&A/extraction validation.",
        )
        (args.output_dir / "recommendation.json").write_text(
            json.dumps(recommendation, indent=2) + "\n"
        )
        lines.extend(
            [
                "## Recommendation",
                "",
                f"Best evidence coverage: {best['profile']} / {best['configuration']} "
                f"(Recall@5 {best['recall']:.4f}). Recommended original-index reranking "
                f"depth: {depth['candidates']}. Keep the scoring correction independently "
                "of retrieval experiments. Grouping remains opt-in; enable it only if its "
                "measured coverage meets the project owner's acceptance criteria.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Recommendation",
                "",
                "Pending: complete both index profiles before deciding on grouping.",
                "",
            ]
        )
    (args.output_dir / "comparison.md").write_text("\n".join(lines))
    print(f"Saved {args.output_dir / 'comparison.md'}", flush=True)


if __name__ == "__main__":
    main()
