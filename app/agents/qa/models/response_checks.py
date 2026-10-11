"""Constrain citation choices and validate the answer returned by QA."""

from app.agents.qa.models.answers import AnswerDraft


def response_schema(model_type, evidence):
    schema = model_type.model_json_schema()
    if "coverage" in schema["properties"]:
        # Groq strict schemas require every property, including fields with Python defaults.
        schema["required"] = list(schema["properties"])
        schema["properties"]["coverage"].pop("default", None)
        schema["properties"]["coverage"]["minItems"] = 1
        coverage_ids = schema["$defs"]["EvidenceCoverage"]["properties"]["source_chunk_ids"]
        if evidence:
            coverage_ids["items"]["enum"] = list(
                dict.fromkeys(item["chunk_id"] for item in evidence)
            )
        else:
            coverage_ids["maxItems"] = 0
    citations = schema["properties"]["source_chunk_ids"]
    if evidence:
        citations["items"]["enum"] = list(dict.fromkeys(item["chunk_id"] for item in evidence))
    else:
        citations["maxItems"] = 0
    return schema


def checked_answer(draft, evidence):
    known_ids = {item["chunk_id"] for item in evidence}
    if not set(draft.source_chunk_ids).issubset(known_ids):
        raise ValueError("Answer cites evidence that was not retrieved")
    if draft.status == "found":
        if not draft.answer.strip() or not draft.source_chunk_ids:
            raise ValueError("Answer needs text and citations")
        return AnswerDraft.model_validate(draft.model_dump(include=set(AnswerDraft.model_fields)))
    return AnswerDraft(status="not_found", answer="Not found in documents", source_chunk_ids=[])
