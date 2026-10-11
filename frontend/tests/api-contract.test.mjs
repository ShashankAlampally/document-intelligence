import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { queryDocuments, uploadFolder, getIndexedFolder } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('Ask and Search send all chat discovery IDs', async () => {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (path, init) => {
    requests.push({ path, body: JSON.parse(init.body) });
    return Response.json({ answer: 'Evidence', sources: [] });
  };
  try {
    for (const mode of ['ask', 'search']) await queryDocuments(['bid-a', 'bid-b'], 'Compare warranties', mode);
    assert.deepEqual(requests, ['ask', 'search'].map(mode => ({ path: `/api/sessions/${mode}`, body: { question: 'Compare warranties', discovery_ids: ['bid-a', 'bid-b'] } })));
  } finally { globalThis.fetch = original; }
});

test('upload preserves folder-relative filename and explicit discovery ID', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (path, init) => {
    assert.equal(path, '/api/sessions');
    assert.equal(init.body.get('files').name, 'Bid1/specs.pdf');
    return Response.json({ id: 'job-a', status: 'ready', discovery_id: 'upload-a' });
  };
  try {
    const file = new File(['document'], 'specs.pdf');
    Object.defineProperty(file, 'webkitRelativePath', { value: 'Bid1/specs.pdf' });
    assert.equal((await uploadFolder([file])).discovery_id, 'upload-a');
  } finally { globalThis.fetch = original; }
});


test('opening an indexed folder only requests its saved metadata', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (path, init) => {
    assert.equal(path, '/api/sessions/existing-id');
    assert.equal(init, undefined);
    return Response.json({ discovery_id: 'existing-id', folder_name: 'Bid1', stored_chunks: 42, files: [] });
  };
  try {
    assert.equal((await getIndexedFolder('existing-id')).stored_chunks, 42);
  } finally { globalThis.fetch = original; }
});

test('opening a removed index preserves the backend explanation', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ detail: 'Vectors were removed. Index the folder again.' }, { status: 409 });
  try {
    await assert.rejects(getIndexedFolder('old-id'), /Vectors were removed/);
  } finally { globalThis.fetch = original; }
});
