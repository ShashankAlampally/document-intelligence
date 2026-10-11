import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';
const source = readFileSync(new URL('../src/lib/saved-bids.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { readSavedBids, rememberBid } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const id = 'e6830bc5-4866-4caa-a2d7-b95f8c9e5b39';
test('saved references survive storage round trips without duplicate IDs', () => {
  const bids = rememberBid(rememberBid([], { discoveryId: id, name: 'Old' }), { discoveryId: id.toUpperCase(), name: 'Bid 1' });
  assert.deepEqual(bids, [{ discoveryId: id, name: 'Bid 1' }]);
  assert.deepEqual(readSavedBids({ getItem: () => JSON.stringify(bids) }), bids);
});
test('blocked, malformed and invalid storage records are handled safely', () => {
  assert.deepEqual(readSavedBids({ getItem() { throw new Error('Blocked'); } }), []);
  assert.deepEqual(readSavedBids({ getItem: () => '{broken' }), []);
  assert.deepEqual(readSavedBids({ getItem: () => JSON.stringify([null, { discoveryId: 'invalid', name: 'Bid' }, { discoveryId: id, name: 'Bid' }, { discoveryId: id.toUpperCase(), name: 'Duplicate' }]) }), [{ discoveryId: id, name: 'Bid' }]);
});
