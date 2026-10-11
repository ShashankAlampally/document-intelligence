import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRequire } from 'node:module';

const temporary = mkdtempSync(join(tmpdir(), 'rfp-presentation-'));
let render;
try {
  const outfile = join(temporary, 'render.cjs');
  await build({ stdin: { contents: `import React from 'react'; import { renderToStaticMarkup } from 'react-dom/server'; import { AnswerContent } from './src/components/AnswerContent'; import { ExtractionContent } from './src/components/ExtractionContent'; import { SourceCards } from './src/components/SourceCards'; export function extraction(text) { return renderToStaticMarkup(<ExtractionContent text={text}/>); } export function answer(text) { return renderToStaticMarkup(<AnswerContent text={text}/>); } export function sources(items, search) { return renderToStaticMarkup(<SourceCards sources={items} search={search} onOpen={() => {}}/>); }`, loader: 'tsx', resolveDir: new URL('..', import.meta.url).pathname }, bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic', outfile, logLevel: 'silent' });
  render = createRequire(import.meta.url)(outfile);
} finally { rmSync(temporary, { recursive: true, force: true }); }

test('formats headings, lists and comparison tables while keeping HTML inert', () => {
  const html = render.answer('## Requirements\n- **RAM**: 16 GB\n- Storage: 512 GB\n\n| Bid | Warranty |\n| --- | --- |\n| Bid1 | 3 years |\n\n<script>alert(1)</script>');
  assert.match(html, /<h3>Requirements<\/h3>/);
  assert.match(html, /<ul>/);
  assert.match(html, /<strong>RAM<\/strong>/);
  assert.match(html, /<table>/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});

test('source cards expose folder and page and search includes exact evidence', () => {
  const source = { file: 'specs.pdf', folder_name: 'Bid2', page: 3, text: 'RAM must be 16 GB', discovery_id: 'private-upload-id', table_id: 'table', table_complete: false };
  const html = render.sources([source], true);
  assert.match(html, /specs.pdf/);
  assert.match(html, /Bid2/);
  assert.match(html, /Page 3/);
  assert.match(html, /RAM must be 16 GB/);
  assert.match(html, /Partial table/);
  assert.doesNotMatch(html, /private-upload-id/);
  assert.doesNotMatch(render.sources([source], false), /RAM must be 16 GB/);
});

test('HTML sources show their section without inventing a page', () => {
  const html = render.sources([{ file: 'bid.html', section: 'Requirements', text: 'Evidence' }], true);
  assert.match(html, /Section: Requirements/);
  assert.doesNotMatch(html, /Page 1/);
});


test('extraction rows preserve values, colons and escaped HTML', () => {
  const html = render.extraction('submission_deadline: 24 November at 15:00\ncontact_email: Not found in documents\nnotes: <script>unsafe</script>');
  assert.match(html, /aria-label="Extracted bid fields"/);
  assert.match(html, /submission deadline/);
  assert.match(html, /24 November at 15:00/);
  assert.match(html, /Not found in documents/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
});

test('unstructured extraction output keeps its full text', () => {
  const html = render.extraction('## Requirements\n- Include signed forms.\nAdditional explanation.');
  assert.match(html, /Include signed forms/);
  assert.match(html, /Additional explanation/);
  assert.doesNotMatch(html, /aria-label="Extracted bid fields"/);
});
