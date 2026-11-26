import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
const source = await readFile(new URL('../src/utils/backgroundMedia.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
const { backgroundInfo, validateSignature } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('GIF stays animated, video formats accept missing browser MIME and case-insensitive names', () => {
  assert.equal(backgroundInfo({ name: '动图.GIF', size: 10 }).kind, 'gif')
  assert.deepEqual(backgroundInfo({ name: '背景.MP4', size: 10 }), { kind: 'video', mime: 'video/mp4' })
  assert.equal(backgroundInfo({ name: 'background.webm', size: 10 }).kind, 'video')
  assert.equal(backgroundInfo({ name: 'background.ogv', size: 10 }).mime, 'video/ogg')
})
test('image and video have separate size limits and unsupported formats fail', () => {
  for (const file of [{ name: 'x.gif', size: 10 * 1024 * 1024 + 1 }, { name: 'x.mp4', size: 50 * 1024 * 1024 + 1 }, { name: 'x.mp4', size: 0 }, { name: 'x.svg', size: 10 }, { name: 'x.mov', size: 10 }]) assert.throws(() => backgroundInfo(file))
  assert.equal(backgroundInfo({ name: 'x.mp4', size: 50 * 1024 * 1024 }).kind, 'video')
})
test('file headers must match the selected format', async () => {
  for (const [name, bytes, mime] of [
    ['x.gif', new TextEncoder().encode('GIF89a'), 'image/gif'],
    ['x.mp4', new Uint8Array([0,0,0,24,102,116,121,112]), 'video/mp4'],
    ['x.webm', new Uint8Array([26,69,223,163]), 'video/webm'],
    ['x.ogv', new TextEncoder().encode('OggS'), 'video/ogg'],
  ]) await validateSignature(new File([bytes], name), mime)
  await assert.rejects(validateSignature(new File(['<svg></svg>'], 'fake.gif'), 'image/gif'))
  await assert.rejects(validateSignature(new File(['broken'], 'fake.mp4'), 'video/mp4'))
})
