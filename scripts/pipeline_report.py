"""Render a trace as a readable audit, without pretending to score accuracy."""

import json
from collections import Counter

from scripts.groq_event_summary import summarize_events


def render_report(record):
    lines = [
        "# Extraction pipeline report",
        "",
        f"Discovery ID: {record['discovery_id']}",
        f"Status: {record['status']}",
        "",
        "Evidence selection and model output are recorded here; accuracy needs a source review.",
        "",
    ]
    total_tokens = 0
    calls = 0
    for step in record.get("trace", []):
        group = step.get("field_group", "unknown")
        if step["step"] == "retrieve_evidence":
            if step.get("error"):
                lines += [
                    f"## {group}: retrieval failed",
                    "",
                    str(step.get("error_detail", step["error"])),
                    "",
                ]
                continue
            selection = step["selection"]
            decisions = Counter(item["decision"] for item in selection.get("decisions", []))
            lines += [
                f"## {group}: retrieval",
                "",
                f"Queries: {len(step['input'])}; candidates: {selection['candidate_count']}; "
                f"selected: {selection['selected_count']}.",
                f"Evidence size: {selection['serialized_chars']} / {selection['max_chars']} chars; "
                f"chunk cap: {selection['max_chunks']}.",
                f"Selection decisions: {dict(decisions)}.",
                "",
            ]
            selected = {item["chunk_id"] for item in step["output"]}
            for search in step.get("search_results", []):
                request = search["request"]
                lines += [f"**{request.get('field_name', 'QA')}** — {request['query']}", ""]
                for rank, chunk in enumerate(search["chunks"], 1):
                    label = (
                        "selected"
                        if chunk["chunk_id"] in selected
                        else "omitted (see JSON decisions)"
                    )
                    lines.append(
                        f"- Rank {rank}: `{chunk['chunk_id']}`; {chunk['file_name']}; "
                        f"page {chunk.get('page_number')}; {label}; "
                        f"rerank={chunk.get('rerank_score')}"
                    )
                lines.append("")
            if selection["queries_without_selected_evidence"]:
                lines += [
                    "Queries without selected IDs (duplicate content may still provide coverage):",
                    *[f"- {query}" for query in selection["queries_without_selected_evidence"]],
                    "",
                ]
            for chunk in step["output"]:
                lines += [
                    f"### Selected evidence: {chunk['chunk_id']}",
                    "",
                    f"Source: {chunk['file_name']}; page {chunk.get('page_number')}; "
                    f"context {chunk.get('heading_context')}",
                    "",
                    "```text",
                    chunk["text"],
                    "```",
                    "",
                ]
        elif step["step"] == "validate_fields":
            calls += int(step.get("model_called", False))
            usage = step.get("usage", {})
            total_tokens += usage.get("total_tokens", 0)
            lines += [
                "## Combined validation",
                "",
                f"Batch {step.get('batch_index')} / {step.get('batch_count')}; "
                f"correction attempt {step.get('correction_attempts')}; usage: {usage}",
                "",
            ]
            if step.get("error"):
                lines += [f"Error: {step.get('error_detail', step['error'])}", ""]
            else:
                for field in step.get("output", {}).get("fields", []):
                    lines += [f"**{field['name']}**: {field['decision']}", field["reason"], ""]
        elif step["step"] == "extract_fields":
            calls += int(step.get("model_called", True))
            usage = step.get("usage", {})
            total_tokens += usage.get("total_tokens", 0)
            lines += [
                f"## {group}: model output",
                "",
                f"Elapsed: {step.get('latency_seconds', 0):.1f}s; usage: {usage}",
                "",
            ]
            if step.get("error"):
                lines += [f"Error: {step.get('error_detail', step['error'])}", ""]
            else:
                for field in step["output"]["fields"]:
                    lines += [
                        f"**{field['name']}**: {field['value']}",
                        f"Cited chunks: {field['source_chunk_ids']}",
                        f"Notes: {field.get('notes')}",
                        "",
                    ]
    lines += [
        "## Run totals",
        "",
        f"Model attempts recorded: {calls}; reported tokens: {total_tokens}.",
        "The shared Groq client manages retries; trace entries do not count HTTP attempts.",
        "",
    ]
    diagnostics = record.get("groq_diagnostics", {})
    if diagnostics:
        lines += [
            "## Groq events for this run",
            "",
            f"HTTP attempts: {diagnostics['http_attempts']}; "
            f"retries scheduled: {diagnostics['retries_scheduled']}; "
            f"observed waits: {diagnostics['observed_wait_seconds']:.2f}s.",
            f"Provider errors by status: {diagnostics['provider_errors']}.",
            "Full timestamped requests, errors and wait events are in events.jsonl.",
            "",
        ]
    baseline = record.get("baseline", {})
    if baseline:
        lines += ["## Changes from saved baseline", ""]
        for name, field in record.get("fields", {}).items():
            previous = baseline.get("fields", {}).get(name, {}).get("value")
            if previous != field["value"]:
                lines += [f"**{name}**", f"Before: {previous}", f"After: {field['value']}", ""]
    return "\n".join(lines)


def save_record(directory, record):
    directory.mkdir(parents=True, exist_ok=True)
    record["groq_diagnostics"] = summarize_events(directory)
    (directory / "trace.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    result = {key: value for key, value in record.items() if key not in {"trace", "baseline"}}
    (directory / "fields.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    (directory / "report.md").write_text(render_report(record))
    if record["status"] == "completed":
        latest = {**record, "trace": latest_group_steps(record)}
        note = "Latest steps per group. Full test/retry history is in report.md and trace.json.\n\n"
        (directory / "final-evidence-report.md").write_text(note + render_report(latest))


def latest_group_steps(record):
    """Show the latest steps per group; keep the full history in trace.json."""
    groups = {}
    for step in record.get("trace", []):
        group = step.get("field_group", "unknown")
        key = step["step"]
        if key == "validate_fields":
            key = (key, step.get("correction_attempts"), step.get("batch_index"))
        groups.setdefault(group, {})[key] = step
    return [step for stages in groups.values() for step in stages.values()]
