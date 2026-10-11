import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

// Transpile the isolated utility in memory: no browser, network, or test framework.
const source = readFileSync(new URL('../src/lib/sequential-folder-processing.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { processFoldersSequentially } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const folder = (id, discoveryId) => ({ id, name: id, files: [], discoveryId });

test('waits for each folder and returns every discovery ID', async () => {
  let active = 0;
  const processed = [];
  const progress = [];
  const ids = await processFoldersSequentially([folder('a'), folder('b')], async value => {
    active++;
    assert.equal(active, 1);
    await new Promise(resolve => setTimeout(resolve, 2));
    processed.push(value.id);
    active--;
    return `discovery-${value.id}`;
  }, (id, status) => progress.push([id, status.status]));
  assert.deepEqual(ids, ['discovery-a', 'discovery-b']);
  assert.deepEqual(processed, ['a', 'b']);
  assert.deepEqual(progress, [['a', 'processing'], ['a', 'ready'], ['b', 'processing'], ['b', 'ready']]);
});

test('retry skips successful folders and stops after failure', async () => {
  const processed = [];
  const progress = [];
  await assert.rejects(processFoldersSequentially([folder('a', 'existing-a'), folder('b'), folder('c')], async value => {
    processed.push(value.id);
    throw new Error('Indexing failed');
  }, (id, status) => progress.push([id, status.status])), /Indexing failed/);
  assert.deepEqual(processed, ['b']);
  assert.deepEqual(progress, [['b', 'processing'], ['b', 'failed']]);
});

test('never marks an upload ready without its ID', async () => {
  const progress = [];
  await assert.rejects(processFoldersSequentially([folder('a')], async () => '', (_, status) => progress.push(status)), /discovery ID/);
  assert.equal(progress.at(-1).status, 'failed');
});
