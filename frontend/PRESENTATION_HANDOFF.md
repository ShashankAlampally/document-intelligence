# Presentation and backend follow-up

The current UI uses the existing DocumentReply and SourcePassage fields. It formats a small Markdown subset (headings, bold, inline code, simple lists, fenced code and pipe tables), safely as React text. Raw HTML and model-provided links are not executed. Source cards show file/folder/page or section; Search displays exact passages. Evidence supports previous/next, copying, optional table completeness, and expandable retrieval scores. PDF links use local uploaded File objects and browser PDF support; page navigation is a viewer hint, not guaranteed exact positioning. Ambiguous filenames suppress the link.

No backend changes are necessary for this first presentation pass. Full browser interaction QA remains separate from component rendering and build checks.

## Backend additions needed next

1. Add optional `extraction` to DocumentReply containing discovery_id, fields with value/sources/confidence/notes, addendum_changes and validation. Preserve the structured extraction already produced by the graph rather than flattening it into answer text. This enables field tables and accurate JSON download. Do not parse display text back into fields.
2. For inline claim citations, return answer blocks/claims with explicit source_chunk_ids. The client currently cannot associate individual claims with the independent source list reliably.
3. For precise evidence highlighting, return quoted spans or start/end offsets into the exact returned source.text, tied to the claim/field. For original PDF highlights, add page bounding boxes; passage offsets alone are insufficient.
4. Return source.relative_path (and ideally a stable document ID) to distinguish same-named documents in nested folders. Existing file basename plus discovery_id cannot always identify the original upload uniquely.
5. For structured notice displays, optionally return per-file parsing issues and chunk counts on ProcessingJob. The UI currently receives only job.detail's aggregate notice count.

If source retrieval after browser refresh is later required, add a scoped read-only original-document endpoint with appropriate access controls. No such endpoint is required while files remain in local React state.
