import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/utils/folderTree.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const { folderRows } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
const folder = (id, parent_id, name = id) => ({ id, parent_id, name, revision: 'r' })

test('nested folders retain paths and hidden descendants remain usable in selectors', () => {
  const rows = folderRows([folder('child', 'root'), folder('root', null), folder('leaf', 'child'), folder('other', null)], new Set(['root']))
  assert.deepEqual(rows.map(r => [r.folder.id, r.depth, r.visible]), [['root', 0, true], ['child', 1, false], ['leaf', 2, false], ['other', 0, true]])
  assert.equal(rows[2].path, 'root / child / leaf')
  assert.equal(folderRows([folder('r', null)], new Set())[0].hasChildren, false)
})

test('deep nesting uses iterative traversal', () => {
  const input = Array.from({ length: 2000 }, (_, i) => folder(String(i), i ? String(i - 1) : null))
  const rows = folderRows(input, new Set())
  assert.equal(rows.length, 2000)
  assert.equal(rows.at(-1).depth, 1999)
})
