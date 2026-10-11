"""Build instructions for whichever field group is being extracted."""

from app.agents.extraction.models.field_catalog import FIELD_GUIDANCE

FIELD_OUTPUT_INSTRUCTIONS = """Return exactly one JSON entry per requested field,
using only retrieved evidence. Each entry has name, value, source_chunk_ids,
confidence and notes. Values are text or null. A non-null value requires exact
retrieved chunk IDs. Missing fields use null, [], 0 and notes='Not found in
retrieved evidence'. Missing retrieval does not prove absence from the documents.
Explicit negative requirements may be reported as text; absence alone is not 'No'.
Confidence is an uncalibrated evidence-support estimate, not search similarity.
When sources give different values for the same field, cite all supporting chunks
and explain both values with their source file and page/section in notes.
If an addendum explicitly changes that field and its order is established, use
the latest valid updated value in value and explain the original value and change
in notes. An explicit statement that an addendum changes the deadline establishes
precedence over a differing portal listing; a timezone discrepancy does not undo
that explicit change. Preserve the addendum's written time zone without conversion.
Unrelated addendums do not override the field. Search rank or similarity
does not establish precedence. Do not invent an earlier value absent from evidence.
If precedence is unclear, use value=null, cite the conflicting evidence, set
confidence=0, and explain both values and the unresolved conflict in notes.
Null with citations means unresolved conflict; null without citations means missing.
Preserve stated dates, time zones and relative windows; do not invent details.
A bidder question is not an official requirement: use the official Answer when present.
Never infer "not required" from equipment having an operating system already installed.
Preserve who each rule applies to: district, prime vendor, subcontractor or supplier.
Multiple permitted options or cooperative arrangements are not conflicting values;
list all supported options and explain whether participation is optional.
Keep device categories separate. Do not transfer specifications from one category to another.
Use a heading_context only to identify a passage's category; it supplies no missing specifications.
Do not assume a warranty, operating system, quantity or other unstated value.
For broad fields, enumerate all categories supported by the supplied evidence and
explicitly identify incomplete coverage. Do not turn a subset into an all-devices claim.
If a fixed delivery date is absent but scheduling or a relative window is supported,
report that information and say the fixed date is not established.
Table evidence with table_complete=false is partial; do not claim a complete list.
"""


def describe_fields(names: list[str]) -> str:
    return "\n".join(f"- {name}: {FIELD_GUIDANCE[name]}" for name in names)


def field_output_instructions(names: list[str]) -> str:
    return FIELD_OUTPUT_INSTRUCTIONS + "\nRequested fields:\n" + describe_fields(names)
