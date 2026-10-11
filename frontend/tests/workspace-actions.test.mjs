import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

async function load(relative) {
  const source = readFileSync(new URL(relative, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
}
const { hasParsingNotices } = await load('../src/features/folder-upload/processing-notices.ts');
const { extractionRequest } = await load('../src/features/extraction/extraction-request.ts');
const { queryDocuments } = await load('../src/lib/api.ts');

test('distinguishes partial-processing notices from a clean successful job', () => {
  assert.equal(hasParsingNotices('Indexed 42 chunks. 3 parsing notices.'), true);
  assert.equal(hasParsingNotices('Indexed 42 chunks. 0 parsing notices.'), false);
  assert.equal(hasParsingNotices(undefined), false);
});

test('extraction submits only its selected folder without changing ordinary query scope', async () => {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (path, init) => {
    requests.push({ path, body: JSON.parse(init.body) });
    return Response.json({ answer: 'Fields', sources: [] });
  };
  try {
    const request = extractionRequest('selected-bid');
    await queryDocuments(request.discoveryIds, request.question, request.mode);
    await queryDocuments(['selected-bid', 'other-bid'], 'Compare', 'ask');
    assert.equal(requests[0].path, '/api/sessions/ask');
    assert.deepEqual(requests[0].body.discovery_ids, ['selected-bid']);
    assert.match(requests[0].body.question, /all 20 structured bid fields/);
    assert.deepEqual(requests[1].body.discovery_ids, ['selected-bid', 'other-bid']);
    assert.throws(() => extractionRequest(''), /indexed folder/);
  } finally { globalThis.fetch = original; }
});
