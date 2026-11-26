import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/utils/noteImport.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const { readNoteFile, MAX_IMPORT_BYTES } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('Markdown preserves indentation, CRLF, HTML text and trailing whitespace', async () => {
  const content = '# 标题\r\n\r\n    code\r\nline  \r\n<script>alert(1)</script>'
  assert.deepEqual(await readNoteFile(new File([content], ' 学习.MD')), { title: '学习', content })
})
test('TXT, markdown extension and UTF-8 BOM are supported', async () => {
  assert.deepEqual(await readNoteFile(new File(['\ufeff中文😀'], '记录.txt')), { title: '记录', content: '中文😀' })
  assert.equal((await readNoteFile(new File(['text'], '知识.markdown'))).title, '知识')
})
test('invalid extension, empty, binary, encoding and size fail without truncation', async () => {
  for (const file of [new File(['x'], 'a.pdf'), new File(['x'], 'a.docx'), new File([''], 'a.txt'),
    new File([' \n\t'], 'a.md'), new File(['a\0b'], 'a.txt'),
    new File([new Uint8Array([0xff, 0xfe, 0x61, 0])], 'utf16.txt'),
    new File(['x'.repeat(MAX_IMPORT_BYTES + 1)], 'large.md'), new File(['字'.repeat(100001)], 'long.md')]) {
    await assert.rejects(readNoteFile(file), Error)
  }
})
test('Unicode title and body limits count code points', async () => {
  const result = await readNoteFile(new File(['😀'.repeat(100000)], '😀'.repeat(201) + '.md'))
  assert.equal(Array.from(result.title).length, 200)
  assert.equal(Array.from(result.content).length, 100000)
  await assert.rejects(readNoteFile(new File(['😀'.repeat(100001)], 'long.md')))
})
test('an unreadable file is reported and a blank basename gets a fallback', async () => {
  await assert.rejects(readNoteFile({ name: 'a.txt', size: 1, arrayBuffer: async () => { throw new Error('denied') } }), /无法读取/)
  assert.equal((await readNoteFile(new File(['正文'], '.md'))).title, '导入的笔记')
})
